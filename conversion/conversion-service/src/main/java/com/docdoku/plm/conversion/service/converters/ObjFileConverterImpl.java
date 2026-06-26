
package com.docdoku.plm.conversion.service.converters;


import com.docdoku.plm.server.converters.CADConverter;
import com.docdoku.plm.server.converters.ConversionResultProxy;

import javax.enterprise.context.ApplicationScoped;
import java.net.URI;
import java.nio.file.Path;
import java.nio.file.Paths;

@ApplicationScoped
public class ObjFileConverterImpl implements CADConverter {

    @Override
    public ConversionResultProxy convert(final URI cadFileUri, final URI tmpDirUri)
            throws ConversionException {
        Path tmpCadFile = Paths.get(cadFileUri);
        return new ConversionResultProxy(tmpCadFile);
    }

    @Override
    public boolean canConvertToOBJ(String cadFileExtension) {
        return "obj".equals(cadFileExtension);
    }

}