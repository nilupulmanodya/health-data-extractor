from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

converter = PdfConverter(
    artifact_dict=create_model_dict(),
)
rendered = converter("test_data/test1.pdf")
text, _, images = text_from_rendered(rendered)
print(text)

with open("outputs/output.txt", "w", encoding="utf-8") as f:
    f.write(text)