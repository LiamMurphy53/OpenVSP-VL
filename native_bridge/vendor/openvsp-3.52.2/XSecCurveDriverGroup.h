// Exact declarations from official OpenVSP_3.52.2 src/geom_core/XSecCurve.h.
#pragma once
#include "Parm.h"
class XSecCurve;
class XSecCurveDriverGroup : public DriverGroup
{
public:
    XSecCurveDriverGroup( int Nvar, int Nchoice );

    XSecCurve *m_Parent;

    double m_prevArea;
};

class HWXSecCurveDriverGroup : public XSecCurveDriverGroup
{
public:
    HWXSecCurveDriverGroup();

    virtual void UpdateGroup( vector< string > parmIDs );
    virtual bool ValidDrivers( vector< int > choices );
};

class DXSecCurveDriverGroup : public XSecCurveDriverGroup
{
public:
    DXSecCurveDriverGroup();

    virtual void UpdateGroup( vector< string > parmIDs );
    virtual bool ValidDrivers( vector< int > choices );
};

