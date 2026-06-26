# docdoku-plm-conversion-service

DocDokuPLM microservice that performs file format conversions

Run dev server

```
cd conversion-service
./mvnw compile quarkus:dev
```

Package and build image

./build.sh

Notes

- The Docker image now installs Python dependencies at build time from
	`requirements-converter.txt`.
- Large wheel binaries under `wheels/` are not required in Git anymore and are
	intentionally excluded from version control.
- Build order for Python deps is now:
	1) internal wheelhouse (`CONVERTER_WHEELHOUSE_URL`) if provided
	2) package index fallback (PyPI or mirror)

Example build with internal wheelhouse first:

```
docker build \
  -f Dockerfile.jvm \
  --build-arg CONVERTER_WHEELHOUSE_URL=https://<your-wheelhouse-url>/simple \
  -t docdoku/docdoku-plm-conversion-service:local .
```

Wheel cleanup helper (for local offline cache maintenance):

```
python3 scripts/prune-wheelhouse.py --wheel-dir wheels --target-py cp311
python3 scripts/prune-wheelhouse.py --wheel-dir wheels --target-py cp311 --apply
```
