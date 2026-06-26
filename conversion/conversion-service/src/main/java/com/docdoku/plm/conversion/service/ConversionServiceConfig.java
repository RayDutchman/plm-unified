package com.docdoku.plm.conversion.service;

import javax.inject.Singleton;

@Singleton
public
class ConversionServiceConfig {

    String getHost(){
        return System.getProperty("ENDPOINT","http://back:8080/docdoku-plm-server-rest/api");
    }

    String getVaultPath(){
        return System.getProperty("VAULT_PATH","/data/vault");
    }

    String getConversionsPath(){
        return System.getProperty("CONVERSIONS_PATH","/data/conversions");
    }

    String getDecimaterPath() {
        return "/opt/decimater/openMeshDecimater.sh";
    }

}
