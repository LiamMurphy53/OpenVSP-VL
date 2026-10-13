// Exact class declaration extracted from official OpenVSP_3.52.2
// src/geom_core/WingGeom.h. Full original retained in evidence.
#pragma once
#include "Parm.h"
class WingDriverGroup : public DriverGroup
{
public:

    WingDriverGroup();

    virtual void UpdateGroup( vector< string > parmIDs );
    virtual bool ValidDrivers( vector< int > choices );
};
