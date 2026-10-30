// Draws the app icon (a swept-wing planform on Studio green) into an .iconset folder.
// Usage: swift make_icon.swift <output.iconset>
import AppKit

let out = URL(fileURLWithPath: CommandLine.arguments[1])
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

func draw(_ size: CGFloat) -> Data {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size), pixelsHigh: Int(size), bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = size / 1024
    // macOS icon grid: 824 pt rounded square centred in 1024.
    let tile = NSBezierPath(roundedRect: NSRect(x: 100 * s, y: 100 * s, width: 824 * s, height: 824 * s), xRadius: 185 * s, yRadius: 185 * s)
    NSGradient(starting: NSColor(srgbRed: 0.16, green: 0.55, blue: 0.43, alpha: 1), ending: NSColor(srgbRed: 0.06, green: 0.33, blue: 0.26, alpha: 1))!.draw(in: tile, angle: -90)
    // Top view of an aircraft, nose up.
    let p = NSBezierPath()
    let pts: [(CGFloat, CGFloat)] = [(512, 812), (548, 742), (556, 560), (812, 430), (812, 388), (556, 452), (548, 300), (640, 240), (640, 210), (512, 236),
                                     (384, 210), (384, 240), (476, 300), (468, 452), (212, 388), (212, 430), (468, 560), (476, 742)]
    p.move(to: NSPoint(x: pts[0].0 * s, y: pts[0].1 * s))
    pts.dropFirst().forEach { p.line(to: NSPoint(x: $0.0 * s, y: $0.1 * s)) }
    p.close()
    p.lineJoinStyle = .round
    NSColor.white.setFill()
    p.fill()
    NSGraphicsContext.restoreGraphicsState()
    return rep.representation(using: .png, properties: [:])!
}

for base in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let name = scale == 1 ? "icon_\(base)x\(base).png" : "icon_\(base)x\(base)@2x.png"
        try! draw(CGFloat(base * scale)).write(to: out.appendingPathComponent(name))
    }
}
