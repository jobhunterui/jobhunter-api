import io
from fastapi import UploadFile
from PyPDF2 import PdfReader
from docx import Document
from typing import Union

class CVParserService:
    async def extract_text_from_file(self, file: UploadFile) -> Union[str, None]:
        """
        Extracts text content from an uploaded CV file (PDF or DOCX).
        """
        filename = file.filename
        content_type = file.content_type

        try:
            file_content = await file.read()
            await file.seek(0) # Reset file pointer in case it's read again

            if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
                return self._extract_text_from_pdf(io.BytesIO(file_content))
            elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.lower().endswith(".docx"):
                return self._extract_text_from_docx(io.BytesIO(file_content))
            elif content_type == "application/msword" or filename.lower().endswith(".doc"):
                # Basic .doc support is harder without external libraries like antiword or libreoffice.
                # For now, we can return an error or try a simple extraction if python-docx handles it.
                # python-docx typically does not support .doc files.
                # Consider advising users to convert .doc to .docx or PDF.
                print(f"Attempting to parse .doc file: {filename}. Support is limited.")
                try:
                    # Attempting with python-docx, might fail for older .doc formats
                    return self._extract_text_from_docx(io.BytesIO(file_content))
                except Exception as e:
                    print(f"Could not parse .doc file '{filename}' with python-docx: {e}")
                    raise ValueError("Unsupported .doc file. Please convert to .docx or PDF.")
            elif content_type == "text/plain" or filename.lower().endswith(".txt"):
                return file_content.decode('utf-8')
            else:
                raise ValueError(f"Unsupported file type: {content_type} ({filename}). Please upload a PDF, DOCX, or TXT file.")
        except Exception as e:
            print(f"Error reading or parsing file {filename}: {e}")
            raise ValueError(f"Could not process file: {str(e)}")

    def _extract_text_from_pdf(self, file_stream: io.BytesIO) -> str:
        try:
            reader = PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            raise ValueError("Could not extract text from PDF.")

    def _extract_text_from_docx(self, file_stream: io.BytesIO) -> str:
        try:
            document = Document(file_stream)
            text = ""
            for para in document.paragraphs:
                text += para.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            # python-docx might raise PackageNotFoundError for .doc files
            if "Package not found" in str(e):
                raise ValueError("Unsupported .doc file. Please convert to .docx or PDF.")
            raise ValueError("Could not extract text from DOCX.")

cv_parser_service = CVParserService()