# Gate 2 Kotlin/JVM conformance

This standalone module evaluates the same frozen fixtures as the Python and TypeScript runners. It does not link Android code, call any service, or change the fixture files. The fixture freeze is `d4c05233be9e64addb20e7b62f60d8d5012e6750`.

Use JDK 17. From the repository root on Windows, run:

```powershell
.\android\TrustCaptureVendor\gradlew.bat -p docs/gate-2/conformance/kotlin run --offline
```

This uses the existing Gradle wrapper with the standalone project directory. Gradle does not load the Android project. The offline flag requires the Kotlin 2.0.21 and Gson 2.11.0 build dependencies to be cached.

To run against files exported directly from the frozen Git blobs on Linux or WSL:

```sh
pin=d4c05233be9e64addb20e7b62f60d8d5012e6750
fixture_export=$(mktemp -d)
git archive "$pin" docs/gate-2/fixtures/v1 | tar -x -C "$fixture_export"
bash android/TrustCaptureVendor/gradlew -p docs/gate-2/conformance/kotlin run --offline \
  --args="$fixture_export/docs/gate-2/fixtures/v1"
```

Verified on Windows with JetBrains Runtime 17.0.14 and Gradle 8.11.1. All five exported fixture files matched their Git blob IDs. The run reported **52/52 workflow cases**, **10/10 parser checks**, and **zero discrepancies**.

The runner removes the expected output from the input passed to the evaluator. It compares the computed result afterward. On a mismatch it exits nonzero and reports the fixture filename, case ID, first differing JSON Pointer, and expected and actual values. A temporary negative control changed only the first elevator case's expected `can_submit` value and produced one failure at `/can_submit`. The original fixtures were unchanged.
