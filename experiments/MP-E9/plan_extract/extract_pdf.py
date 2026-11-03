"""MP-E9 / G0-prime: extract the master-plan PDF to text (the pypdf dependency is logged in
experiments/G0-prime/registration.json as a session-added, non-harness tooling dep)."""
from pypdf import PdfReader

r = PdfReader(r"C:/Shared/DROSO_Master_Plan_v1_1.pdf")
text = "".join(f"\n===== PAGE {i + 1} =====\n" + (p.extract_text() or "")
               for i, p in enumerate(r.pages))
open("_tmp/DROSO_Master_Plan_v1_1.txt", "w", encoding="utf-8").write(text)
print("pages:", len(r.pages), "chars:", len(text), "words:", len(text.split()))
