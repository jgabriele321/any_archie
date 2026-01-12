"""
AnyArchie PDF Export
Generates PDF summaries for users
"""
import os
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from . import db


def generate_weekly_summary(user_id: int) -> BytesIO:
    """
    Generate a weekly summary PDF for a user.
    
    Returns:
        BytesIO buffer containing the PDF
    """
    user = None
    # Get user info - we need to fetch by ID
    with db.get_db() as conn:
        with db.dict_cursor(conn) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
    
    if not user:
        raise ValueError("User not found")
    
    # Get context
    context = db.get_all_context(user_id)
    
    # Get tasks
    pending_tasks = db.get_tasks(user_id, status="pending")
    completed_tasks = db.get_tasks(user_id, status="done")
    
    # Filter completed tasks to last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    recent_completed = [
        t for t in completed_tasks 
        if t.get('completed_at') and t['completed_at'] >= week_ago
    ]
    
    # Get upcoming reminders
    reminders = db.get_user_reminders(user_id)
    
    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10
    )
    normal_style = styles['Normal']
    
    story = []
    
    # Title
    today = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Weekly Summary - {today}", title_style))
    story.append(Paragraph(f"For {user.get('user_name', 'User')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Goals/Focus
    if context.get('goals') or context.get('current_focus'):
        story.append(Paragraph("Your Focus", heading_style))
        if context.get('goals'):
            story.append(Paragraph(f"<b>Goals:</b> {context['goals']}", normal_style))
        if context.get('current_focus'):
            story.append(Paragraph(f"<b>Current Focus:</b> {context['current_focus']}", normal_style))
        story.append(Spacer(1, 10))
    
    # Pending Tasks
    story.append(Paragraph("Pending Tasks", heading_style))
    if pending_tasks:
        for i, task in enumerate(pending_tasks[:15], 1):  # Limit to 15
            due = f" (due: {task['due_date']})" if task.get('due_date') else ""
            story.append(Paragraph(f"{i}. {task['content']}{due}", normal_style))
    else:
        story.append(Paragraph("No pending tasks!", normal_style))
    story.append(Spacer(1, 10))
    
    # Completed This Week
    story.append(Paragraph("Completed This Week", heading_style))
    if recent_completed:
        for task in recent_completed[:10]:  # Limit to 10
            story.append(Paragraph(f"✓ {task['content']}", normal_style))
    else:
        story.append(Paragraph("No tasks completed this week.", normal_style))
    story.append(Spacer(1, 10))
    
    # Upcoming Reminders
    if reminders:
        story.append(Paragraph("Upcoming Reminders", heading_style))
        for r in reminders[:5]:  # Limit to 5
            time_str = r['remind_at'].strftime("%a %b %d at %I:%M %p")
            story.append(Paragraph(f"• {time_str}: {r['message']}", normal_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_task_export(user_id: int) -> BytesIO:
    """
    Generate a simple task list PDF.
    
    Returns:
        BytesIO buffer containing the PDF
    """
    tasks = db.get_tasks(user_id, status="pending")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    today = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Task List - {today}", styles['Heading1']))
    story.append(Spacer(1, 20))
    
    if tasks:
        for i, task in enumerate(tasks, 1):
            due = f" (due: {task['due_date']})" if task.get('due_date') else ""
            story.append(Paragraph(f"☐ {task['content']}{due}", styles['Normal']))
            story.append(Spacer(1, 5))
    else:
        story.append(Paragraph("No pending tasks!", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer
