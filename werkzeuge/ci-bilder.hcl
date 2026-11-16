# Images für die Browsertests der CI (.github/workflows/backend.yml): beide gleichzeitig bauen, mit Zwischenspeicher
# der GitHub Actions (Abhängigkeiten, Systempakete und OCR-Modelle ändern sich selten – nur die Quellen werden neu
# gebaut). Gleiche Dockerfiles wie auf dem Server (werkzeuge/ci-stack.sh baut ohne Zwischenspeicher genauso).
# Tag wie im Betrieb (X.Y.Z-Commit): der Systemagent erkennt nur solche Versionen (TAG_MUSTER) – mit „ci“ blieben
# „Software“ und das Notfallpaket ohne laufende Version (Browsertests system.spec.ts)
variable "EPM_CI_TAG" {
  default = "ci"
}

group "default" {
  targets = ["backend", "web"]
}

target "backend" {
  context = "backend"
  tags    = ["epm-backend:${EPM_CI_TAG}"]
}

target "web" {
  context = "frontend"
  tags    = ["epm-web:${EPM_CI_TAG}"]
}
