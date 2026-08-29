from dataclasses import dataclass
from typing import Any
from core.content_normalizer import ContentNormalizer
from core.pdf_analyzer import PageAnalysis
from core.pdf_reader import PDFReader
from core.ocr_engine import OCREngine
from core.text_fragment import TextFragment

@dataclass
class ProcessedPage:
    page_number:int
    text:str
    lines:list[str]
    source:str
    scores:list[float]|None=None
    boxes:Any=None
    fragments:list[TextFragment]|None=None
    raw_text:str=""
    quality_score:float=0.0
    normalization_method:str=""

class PageProcessor:
    def __init__(self, reader:PDFReader, ocr:OCREngine|None=None, normalizer:ContentNormalizer|None=None):
        self.reader=reader; self.ocr=ocr; self.normalizer=normalizer or ContentNormalizer()

    def process(self,page:PageAnalysis)->ProcessedPage:
        if page.has_text:
            raw=self.reader.get_page_text(page.page_number-1)
            fragments=self.reader.get_page_fragments(page.page_number-1)
            n=self.normalizer.normalize(raw,fragments,source="pdf_text")
            return ProcessedPage(page.page_number,n.text,n.text.splitlines(),"pdf_text",fragments=fragments,raw_text=raw,quality_score=n.quality_score,normalization_method=n.method)
        if self.ocr is None: self.ocr=OCREngine()
        result=self.ocr.process(self.reader.get_page_image(page.page_number-1),page.page_number)
        fragments=self._ocr_fragments(result)
        n=self.normalizer.normalize(result.text,fragments,source="ocr")
        return ProcessedPage(page.page_number,n.text,n.text.splitlines(),"ocr",result.scores,result.boxes,fragments,result.text,n.quality_score,n.method)

    @staticmethod
    def _ocr_fragments(result)->list[TextFragment]:
        out=[]
        if result.boxes is None:return out
        for i,text in enumerate(result.lines):
            if not text.strip():continue
            conf=result.scores[i] if i<len(result.scores) else None
            try:
                x1,y1,x2,y2=[float(v) for v in result.boxes[i]]
                vals=(x1,y1,x2-x1,y2-y1)
            except (TypeError,ValueError,IndexError): vals=(None,None,None,None)
            out.append(TextFragment(text=text.strip(),x=vals[0],y=vals[1],confidence=conf,width=vals[2],height=vals[3]))
        return out
