// OpenVSP Studio for macOS: a native window around the local Studio server.
// The app starts (or reuses) the server through studio_launcher.py, shows the
// interface in WebKit, and gives it native menus, file panels and downloads.
import AppKit
import WebKit

final class StudioApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var root: URL!
    var server: URL?
    var startedServer = false
    var downloads: [WKDownload: URL] = [:]

    // MARK: Launch

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.allowsMagnification = true
        web.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "OpenVSP Studio"
        window.minSize = NSSize(width: 980, height: 640)
        window.backgroundColor = NSColor(srgbRed: 0.976, green: 0.98, blue: 0.969, alpha: 1)
        window.contentView = web
        window.setFrameAutosaveName("StudioMainWindow")
        if !window.setFrameUsingName("StudioMainWindow") { window.center() }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        showMessage("Starting OpenVSP…", detail: "Loading the engine. This takes a few seconds the first time.", spinner: true)
        guard let found = locateRoot() else {
            fail("The OpenVSP Studio folder could not be found. Run tools/install_app.sh again from the project folder.")
            return
        }
        root = found
        startServer()
    }

    func locateRoot() -> URL? {
        let fm = FileManager.default
        var candidates: [URL] = []
        if let saved = Bundle.main.object(forInfoDictionaryKey: "StudioRoot") as? String { candidates.append(URL(fileURLWithPath: saved)) }
        candidates.append(Bundle.main.bundleURL.deletingLastPathComponent())
        return candidates.first { fm.fileExists(atPath: $0.appendingPathComponent("studio_launcher.py").path) }
    }

    func startServer() {
        let python = root.appendingPathComponent(".runtime/python-interpreters/cpython-3.11-macos-aarch64-none/bin/python3")
        let process = Process()
        process.executableURL = FileManager.default.isExecutableFile(atPath: python.path) ? python : URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [root.appendingPathComponent("studio_launcher.py").path, "--no-open"]
        process.currentDirectoryURL = root
        let out = Pipe(), err = Pipe()
        process.standardOutput = out
        process.standardError = err
        process.terminationHandler = { p in
            let text = String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let problem = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            DispatchQueue.main.async {
                // The launcher prints "Started|Reusing OpenVSP Studio: http://127.0.0.1:PORT/".
                guard p.terminationStatus == 0, let range = text.range(of: "http://127.0.0.1:"),
                      let url = URL(string: String(text[range.lowerBound...]).trimmingCharacters(in: .whitespacesAndNewlines)) else {
                    self.fail(problem.isEmpty ? "Studio could not start." : problem)
                    return
                }
                self.server = url
                self.startedServer = text.hasPrefix("Started")
                self.web.load(URLRequest(url: url))
            }
        }
        do { try process.run() } catch { fail("Could not run the Studio launcher: \(error.localizedDescription)") }
    }

    func showMessage(_ title: String, detail: String, spinner: Bool) {
        let esc = { (s: String) in s.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;") }
        web.loadHTMLString("""
        <!doctype html><meta charset="utf-8"><style>
        body{margin:0;height:100vh;display:grid;place-items:center;background:#f9faf7;color:#243634;font:15px -apple-system,system-ui}
        div{max-width:560px;text-align:center;padding:24px} h1{font-size:22px;font-weight:600;margin:18px 0 8px}
        p{color:#6f7c76;line-height:1.5;white-space:pre-wrap;margin:0}
        i{display:inline-block;width:26px;height:26px;border-radius:50%;border:3px solid #dbe8df;border-top-color:#176e56;animation:s .9s linear infinite}
        @keyframes s{to{transform:rotate(360deg)}}
        @media (prefers-color-scheme:dark){body{background:#1c2422;color:#e6ece9}p{color:#9aa8a2}}
        </style><div>\(spinner ? "<i></i>" : "")<h1>\(esc(title))</h1><p>\(esc(detail))</p></div>
        """, baseURL: nil)
    }

    func fail(_ message: String) {
        showMessage("Studio could not open", detail: message.trimmingCharacters(in: .whitespacesAndNewlines), spinner: false)
    }

    // MARK: Quit

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let server, let jobs = fetchJSON(server.appendingPathComponent("api/jobs")) as? [[String: Any]] else { return .terminateNow }
        if jobs.contains(where: { ($0["status"] as? String) == "running" }) {
            let alert = NSAlert()
            alert.messageText = "An analysis is still running"
            alert.informativeText = "Quitting stops it. Finished runs are kept."
            alert.addButton(withTitle: "Quit")
            alert.addButton(withTitle: "Keep Working")
            if alert.runModal() != .alertFirstButtonReturn { return .terminateCancel }
        }
        return .terminateNow
    }

    func applicationWillTerminate(_ note: Notification) {
        // Leave servers this app reused (a browser may still be using them).
        guard startedServer, let server,
              let health = fetchJSON(server.appendingPathComponent("api/health")) as? [String: Any],
              let pid = health["processID"] as? Int32 else { return }
        kill(pid, SIGTERM)
    }

    func fetchJSON(_ url: URL) -> Any? {
        var result: Any?
        let done = DispatchSemaphore(value: 0)
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5
        URLSession.shared.dataTask(with: request) { data, _, _ in
            if let data { result = try? JSONSerialization.jsonObject(with: data) }
            done.signal()
        }.resume()
        _ = done.wait(timeout: .now() + 2)
        return result
    }

    // MARK: Menus

    func buildMenu() {
        let main = NSMenu()
        func menu(_ title: String, _ items: [NSMenuItem]) {
            let holder = NSMenuItem()
            let m = NSMenu(title: title)
            items.forEach(m.addItem)
            holder.submenu = m
            main.addItem(holder)
        }
        func item(_ title: String, _ action: Selector?, _ key: String = "", _ mods: NSEvent.ModifierFlags = .command, tag: Int = 0) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
            i.keyEquivalentModifierMask = mods
            i.tag = tag
            return i
        }
        menu("OpenVSP Studio", [
            item("About OpenVSP Studio", #selector(NSApplication.orderFrontStandardAboutPanel(_:))),
            .separator(),
            item("Hide OpenVSP Studio", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:))),
            .separator(),
            item("Quit OpenVSP Studio", #selector(NSApplication.terminate(_:)), "q"),
        ])
        menu("File", [
            item("Open Aircraft…", #selector(openModel), "o"),
            item("Save Aircraft As…", #selector(saveModel), "s"),
            .separator(),
            item("Open in Classic OpenVSP", #selector(openNative), "o", [.command, .shift]),
            .separator(),
            item("Close Window", #selector(NSWindow.performClose(_:)), "w"),
        ])
        menu("Edit", [
            item("Undo", #selector(undoStudio), "z"),
            item("Redo", #selector(redoStudio), "z", [.command, .shift]),
            .separator(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
        ])
        menu("View", [
            item("Design", #selector(showPage(_:)), "1", tag: 1),
            item("Modeling Tools", #selector(showPage(_:)), "2", tag: 2),
            item("Analyze", #selector(showPage(_:)), "3", tag: 3),
            item("Studies", #selector(showPage(_:)), "4", tag: 4),
            .separator(),
            item("Actual Size", #selector(zoomReset), "0"),
            item("Zoom In", #selector(zoomIn), "="),
            item("Zoom Out", #selector(zoomOut), "-"),
            .separator(),
            item("Reload", #selector(reload), "r"),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"))
        windowMenu.addItem(item("Zoom", #selector(NSWindow.performZoom(_:))))
        let windowHolder = NSMenuItem()
        windowHolder.submenu = windowMenu
        main.addItem(windowHolder)
        NSApp.windowsMenu = windowMenu
        NSApp.mainMenu = main
    }

    func click(_ selector: String) {
        web.evaluateJavaScript("document.querySelector('\(selector)')?.click()")
    }
    @objc func openModel() { click("#open") }
    @objc func saveModel() { click("#save") }
    @objc func openNative() { click("#native") }
    // Text fields keep their own undo; elsewhere the shortcut means aircraft undo.
    @objc func undoStudio() { web.evaluateJavaScript("(e=>e&&/INPUT|TEXTAREA/.test(e.tagName)?document.execCommand('undo'):document.querySelector('#undo')?.click())(document.activeElement)") }
    @objc func redoStudio() { web.evaluateJavaScript("(e=>e&&/INPUT|TEXTAREA/.test(e.tagName)?document.execCommand('redo'):document.querySelector('#redo')?.click())(document.activeElement)") }
    @objc func showPage(_ sender: NSMenuItem) {
        let page = ["", "design", "tools", "analyze", "studies"][sender.tag]
        click("[data-page=\"\(page)\"]")
    }
    @objc func zoomReset() { web.pageZoom = 1 }
    @objc func zoomIn() { web.pageZoom = min(web.pageZoom + 0.1, 2) }
    @objc func zoomOut() { web.pageZoom = max(web.pageZoom - 0.1, 0.6) }
    @objc func reload() { if let server { web.load(URLRequest(url: server)) } }

    // MARK: Navigation and downloads

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, preferences: WKWebpagePreferences, decisionHandler: @escaping (WKNavigationActionPolicy, WKWebpagePreferences) -> Void) {
        if action.shouldPerformDownload { decisionHandler(.download, preferences); return }
        if let url = action.request.url, let host = url.host, !["127.0.0.1", "localhost"].contains(host), action.navigationType == .linkActivated {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel, preferences)
            return
        }
        decisionHandler(.allow, preferences)
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        decisionHandler(disposition.lowercased().hasPrefix("attachment") || !response.canShowMIMEType ? .download : .allow)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedFilename
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { choice in
            guard choice == .OK, let url = panel.url else { completionHandler(nil); return }
            try? FileManager.default.removeItem(at: url)
            self.downloads[download] = url
            completionHandler(url)
        }
    }

    func downloadDidFinish(_ download: WKDownload) {
        if let url = downloads.removeValue(forKey: download) { NSWorkspace.shared.activateFileViewerSelecting([url]) }
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        downloads.removeValue(forKey: download)
        NSAlert(error: error).beginSheetModal(for: window)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { lostServer(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { lostServer(error) }
    func lostServer(_ error: Error) {
        let code = (error as NSError).code
        guard server != nil, code != NSURLErrorCancelled, code != 102 else { return }
        fail("The Studio engine stopped responding (\(error.localizedDescription)). Choose View → Reload to try again, or quit and reopen the app.")
    }

    // MARK: Panels the page asks for

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let alert = NSAlert()
        alert.messageText = prompt
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 280, height: 24))
        field.stringValue = defaultText ?? ""
        alert.accessoryView = field
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }
}

let app = NSApplication.shared
let delegate = StudioApp()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
