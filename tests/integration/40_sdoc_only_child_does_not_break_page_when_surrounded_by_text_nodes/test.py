from pypdf import PdfReader

reader = PdfReader("Output/index.pdf")

assert len(reader.pages) == 4, len(reader.pages)

#
# Verify that texts are exactly like expected. This prevents the test from
# passing wrongly on the correct page size but incorrect content.
# Besides other things, this ensures that there is no regression when
# html2pdf4doc prints the whole <body> tag instead the one specified with the
# html2pdf4doc(current)/html2pdf(legacy) attribute.
# NOTE: The replace() calls are needed because of the portability issues.
#

assert (
    reader.pages[2].extract_text()
    == """\
1. Section 1
Vivamus consectetur mollis varius. Quisque posuere venenatis nulla, sit amet
pulvinar metus vestibulum sed. Sed at libero nec justo leo.
StrictDoc Documentation Test document
3/4
2025-12-21\
"""
), reader.pages[2].extract_text().replace(".StrictDoc", "\nStrictDoc")

assert (
    reader.pages[3].extract_text()
    == """\
2. Section 2
Lorem ipsum dolor sit amet, c
StrictDoc Documentation Test document
4/4
2025-12-21\
"""
), reader.pages[3].extract_text().replace("cStrictDoc", "c\nStrictDoc")
