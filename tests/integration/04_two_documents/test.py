from pypdf import PdfReader

reader = PdfReader("Output/index1.pdf")
assert len(reader.pages) == 1
assert reader.pages[0].extract_text() == "Hello world!"

reader = PdfReader("Output/index2.pdf")
assert len(reader.pages) == 1
assert reader.pages[0].extract_text() == "Hello world!"
