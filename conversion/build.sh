#!/bin/sh

set -e

VERSION=$(mvn -q -N org.codehaus.mojo:exec-maven-plugin:3.0.0:exec \
    -Dexec.executable='echo' \
    -Dexec.args='${project.version}')

mvn clean install
docker build -f Dockerfile.jvm -t docdoku/docdoku-plm-conversion-service:$VERSION .