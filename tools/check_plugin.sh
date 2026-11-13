#!/usr/bin/env bash
# Compile-checks src/*.cs as C# 6 against the .NET 3.5 profile and the API stubs in
# tools/stubs (VaM itself is not needed). This catches syntax errors, C# 7+ features and
# typos, but NOT wrong assumptions about the real VaM API: the stubs encode those
# assumptions. Requires the .NET SDK (6+).
set -euo pipefail
cd "$(dirname "$0")/stubs"
dotnet build -nologo -v q CheckPlugin.csproj
