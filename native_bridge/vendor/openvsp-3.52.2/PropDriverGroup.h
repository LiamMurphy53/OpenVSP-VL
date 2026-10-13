// Exact class declaration extracted from official OpenVSP_3.52.2
// src/geom_core/VSPAEROMgr.h. Full original retained in evidence.
#pragma once
#include "Parm.h"
class PropDriverGroup : public DriverGroup
{
public:
    PropDriverGroup();

    virtual void UpdateGroup( vector< string > parmIDs );
    virtual bool ValidDrivers( vector< int > choices );

    double Vinf;
    double rho;
    double D;
};

