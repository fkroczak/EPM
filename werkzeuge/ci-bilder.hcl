# Images für die Browsertests der CI (.github/workflows/backend.yml): beide gleichzeitig bauen, mit Zwischenspeicher
# der GitHub Actions (Abhängigkeiten, Systempakete und OCR-Modelle ändern sich selten – nur die Quellen werden neu
# gebaut). Gleiche Dockerfiles wie auf dem Server (werkzeuge/ci-stack.sh baut ohne Zwischenspeicher genauso).
group "default" {
  targets = ["backend", "web"]
}

target "backend" {
  context = "backend"
  tags    = ["epm-backend:ci"]
}

target "web" {
  context = "frontend"
  tags    = ["epm-web:ci"]
}
