from sqlalchemy import select
from fastapi import HTTPException
from reportlab.pdfgen import canvas
from io import BytesIO
from fastapi.responses import StreamingResponse

def generate_pdf(paper_id, design, subject_name, medium_name, exam_type_name, qns_list, total_questions, total_time,include_answers):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f"Question Paper {paper_id}")
    pdf.drawString(100, 800, f"Exam Name: {design.dm_design_name}")
    pdf.drawString(100, 780, f"Paper ID: {paper_id}")
    pdf.drawString(100, 760, f"Subject: {subject_name}")
    pdf.drawString(100, 740, f"Medium: {medium_name}")
    pdf.drawString(100, 720, f"Exam Type: {exam_type_name}")
    pdf.drawString(100, 700, f"Total Questions: {total_questions}")
    pdf.drawString(100, 680, f"Total Time(In Minutes): {total_time}")

    y = 650
    for idx, question in enumerate(qns_list, start=1):
        pdf.drawString(100, y, f"Q{idx}: {question.text}")
        y -= 20

        correct_option_id = None
        for opt in question.options:
            pdf.drawString(120, y, f"{opt.id}. {opt.text}")
            if include_answers and getattr(opt, "is_correct", False):
                correct_option_id = opt.id
            y -= 20

        if include_answers and correct_option_id:
            pdf.drawString(120, y, f"Correct answer: {correct_option_id}")
            y -= 20

        y -= 10
        if y < 100:
            pdf.showPage()
            y = 800

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={paper_id}.pdf",
            "Content-Type": "application/pdf"
        }
    )