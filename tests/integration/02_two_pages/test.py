from pypdf import PdfReader

reader = PdfReader("Output/index.pdf")

assert len(reader.pages) == 3
