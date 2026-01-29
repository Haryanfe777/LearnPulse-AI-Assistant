"""PDF and HTML report generation for learners and classes.

Generates comprehensive reports that instructors can download and share with families.
"""

from io import BytesIO
from datetime import datetime
from typing import Optional
import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.platypus import Image as RLImage
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  ReportLab not installed. PDF generation disabled.")

from app.services.analytics import get_student_stats, get_class_trends, generate_individualized_feedback
from app.infrastructure.data_loader import get_student_data, get_class_summary


def generate_student_report_html(student_name: str) -> str:
    """
    Generate an HTML report for a single student.
    
    Args:
        student_name: Name of the student
    
    Returns:
        HTML string with complete report
    """
    stats = get_student_stats(student_name)
    if not stats.get("exists"):
        return f"<html><body><h1>No data found for {student_name}</h1></body></html>"
    
    feedback = generate_individualized_feedback(student_name)
    
    # Build HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>LearnPulse AI Report - {student_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #FF8D00 0%, #67CBEE 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
        }}
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
        }}
        .section {{
            background: #f8f9fa;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            border-left: 4px solid #FF8D00;
        }}
        .section h2 {{
            color: #FF8D00;
            margin-top: 0;
        }}
        .metric {{
            display: inline-block;
            background: white;
            padding: 15px 25px;
            margin: 10px 10px 10px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #103D64;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th {{
            background: #103D64;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .feedback {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Student Progress Report</h1>
        <p><strong>{student_name}</strong> • Generated on {datetime.now().strftime("%B %d, %Y")}</p>
    </div>
    
    <div class="section">
        <h2>📈 Performance Overview</h2>
        <div class="metric">
            <div class="metric-label">Average Score</div>
            <div class="metric-value">{stats.get('average_score', 0):.1f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Median Score</div>
            <div class="metric-value">{stats.get('median_score', 0):.1f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Sessions</div>
            <div class="metric-value">{stats.get('total_sessions', 0)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Max Streak</div>
            <div class="metric-value">{stats.get('max_streak_days', 0)} days</div>
        </div>
    </div>
"""
    
    # Concept breakdown table
    if stats.get("concept_breakdown"):
        html += """
    <div class="section">
        <h2>🎯 Concept Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Concept</th>
                    <th>Average Score</th>
                    <th>Attempts</th>
                </tr>
            </thead>
            <tbody>
"""
        for concept in stats["concept_breakdown"]:
            html += f"""
                <tr>
                    <td><strong>{concept['concept']}</strong></td>
                    <td>{concept['avg_score']:.1f}</td>
                    <td>{concept.get('sessions', concept.get('count', 0))}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
    </div>
"""
    
    # Weekly trend
    if stats.get("trend_by_week"):
        html += """
    <div class="section">
        <h2>📅 Weekly Trend</h2>
        <table>
            <thead>
                <tr>
                    <th>Week</th>
                    <th>Average Score</th>
                    <th>Sessions</th>
                </tr>
            </thead>
            <tbody>
"""
        for week in stats["trend_by_week"]:
            html += f"""
                <tr>
                    <td>Week {week['week_number']}</td>
                    <td>{week.get('score', 0):.1f}</td>
                    <td>{week.get('count', 0)}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
    </div>
"""
    
    # Individualized feedback
    html += f"""
    <div class="feedback">
        <h2>💡 Individualized Feedback</h2>
        <div style="white-space: pre-line;">{feedback}</div>
    </div>
    
    <div class="footer">
        <p>Generated by LearnPulse AI Instructor Assistant • For questions, contact support@learnpulse.ai</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_class_report_html(class_id: str) -> str:
    """
    Generate an HTML report for an entire class.
    
    Args:
        class_id: Class identifier
    
    Returns:
        HTML string with complete report
    """
    trends = get_class_trends(class_id)
    class_data = get_class_summary(class_id)
    
    if class_data is None or class_data.empty:
        return f"<html><body><h1>No data found for class {class_id}</h1></body></html>"
    
    # Get student list with averages
    student_stats = []
    unique_students = class_data['student_name'].unique()
    for student in unique_students:
        stats = get_student_stats(student, class_data)
        if stats.get('exists'):
            student_stats.append({
                'name': student,
                'avg_score': stats.get('average_score', 0),
                'sessions': stats.get('total_sessions', 0),
                'streak': stats.get('max_streak_days', 0)
            })
    
    student_stats.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Build HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>LearnPulse AI Class Report - {class_id}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #4ECB71 0%, #67CBEE 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
        }}
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
        }}
        .section {{
            background: #f8f9fa;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            border-left: 4px solid #4ECB71;
        }}
        .section h2 {{
            color: #4ECB71;
            margin-top: 0;
        }}
        .metric {{
            display: inline-block;
            background: white;
            padding: 15px 25px;
            margin: 10px 10px 10px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #103D64;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th {{
            background: #103D64;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .rank {{
            background: #FF8D00;
            color: white;
            padding: 5px 10px;
            border-radius: 50%;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📚 Class Progress Report</h1>
        <p><strong>Class {class_id}</strong> • Generated on {datetime.now().strftime("%B %d, %Y")}</p>
    </div>
    
    <div class="section">
        <h2>📊 Class Overview</h2>
        <div class="metric">
            <div class="metric-label">Total Students</div>
            <div class="metric-value">{len(unique_students)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Class Average</div>
            <div class="metric-value">{class_data['score'].mean():.1f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Total Sessions</div>
            <div class="metric-value">{len(class_data)}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>🏆 Student Rankings</h2>
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Student</th>
                    <th>Avg Score</th>
                    <th>Sessions</th>
                    <th>Max Streak</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for i, student in enumerate(student_stats, 1):
        rank_class = 'rank' if i <= 3 else ''
        html += f"""
                <tr>
                    <td class="{rank_class}">{i}</td>
                    <td><strong>{student['name']}</strong></td>
                    <td>{student['avg_score']:.1f}</td>
                    <td>{student['sessions']}</td>
                    <td>{student['streak']} days</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
    </div>
"""
    
    # Weekly trend
    if trends.get("trend_by_week"):
        html += """
    <div class="section">
        <h2>📅 Class Weekly Trend</h2>
        <table>
            <thead>
                <tr>
                    <th>Week</th>
                    <th>Average Score</th>
                    <th>Total Sessions</th>
                </tr>
            </thead>
            <tbody>
"""
        for week in trends["trend_by_week"]:
            html += f"""
                <tr>
                    <td>Week {week['week_number']}</td>
                    <td>{week.get('score', 0):.1f}</td>
                    <td>{week.get('count', 0)}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
    </div>
"""
    
    html += """
    <div class="footer">
        <p>Generated by LearnPulse AI Instructor Assistant • For questions, contact support@learnpulse.ai</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_student_report_pdf(student_name: str) -> Optional[BytesIO]:
    """
    Generate a PDF report for a single student using ReportLab.
    
    Args:
        student_name: Name of the student
    
    Returns:
        BytesIO buffer containing PDF data, or None if ReportLab unavailable
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    stats = get_student_stats(student_name)
    if not stats.get("exists"):
        return None
    
    feedback = generate_individualized_feedback(student_name)
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#FF8D00'),
        spaceAfter=30,
    )
    story.append(Paragraph(f"📊 Student Progress Report", title_style))
    story.append(Paragraph(f"<b>{student_name}</b>", styles['Heading2']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Performance Overview
    story.append(Paragraph("📈 Performance Overview", styles['Heading2']))
    metrics_data = [
        ['Metric', 'Value'],
        ['Average Score', f"{stats.get('average_score', 0):.1f}"],
        ['Median Score', f"{stats.get('median_score', 0):.1f}"],
        ['Total Sessions', f"{stats.get('total_sessions', 0)}"],
        ['Max Streak Days', f"{stats.get('max_streak_days', 0)}"],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#103D64')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Concept Breakdown
    if stats.get("concept_breakdown"):
        story.append(Paragraph("🎯 Concept Performance", styles['Heading2']))
        concept_data = [['Concept', 'Avg Score', 'Attempts']]
        for concept in stats["concept_breakdown"]:
            concept_data.append([
                concept['concept'],
                f"{concept['avg_score']:.1f}",
                str(concept.get('sessions', concept.get('count', 0)))
            ])
        
        concept_table = Table(concept_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        concept_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#103D64')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(concept_table)
        story.append(Spacer(1, 0.3*inch))
    
    # Individualized Feedback
    story.append(Paragraph("💡 Individualized Feedback", styles['Heading2']))
    feedback_style = ParagraphStyle(
        'Feedback',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=20,
    )
    for line in feedback.split('\n\n'):
        story.append(Paragraph(line.replace('\n', '<br/>'), feedback_style))
        story.append(Spacer(1, 0.1*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1,  # Center
    )
    story.append(Paragraph(
        "Generated by LearnPulse AI Instructor Assistant • support@learnpulse.ai",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_class_report_pdf(class_id: str) -> Optional[BytesIO]:
    """
    Generate a PDF report for an entire class using ReportLab.
    
    Args:
        class_id: Class identifier
    
    Returns:
        BytesIO buffer containing PDF data, or None if ReportLab unavailable
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    class_data = get_class_summary(class_id)
    if class_data is None or class_data.empty:
        return None
    
    # Get student list with averages
    student_stats = []
    unique_students = class_data['student_name'].unique()
    for student in unique_students:
        stats = get_student_stats(student, class_data)
        if stats.get('exists'):
            student_stats.append({
                'name': student,
                'avg_score': stats.get('average_score', 0),
                'sessions': stats.get('total_sessions', 0),
                'streak': stats.get('max_streak_days', 0)
            })
    
    student_stats.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#4ECB71'),
        spaceAfter=30,
    )
    story.append(Paragraph(f"📚 Class Progress Report", title_style))
    story.append(Paragraph(f"<b>Class {class_id}</b>", styles['Heading2']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Class Overview
    story.append(Paragraph("📊 Class Overview", styles['Heading2']))
    overview_data = [
        ['Metric', 'Value'],
        ['Total Students', str(len(unique_students))],
        ['Class Average', f"{class_data['score'].mean():.1f}"],
        ['Total Sessions', str(len(class_data))],
    ]
    
    overview_table = Table(overview_data, colWidths=[3*inch, 2*inch])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#103D64')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Student Rankings
    story.append(Paragraph("🏆 Student Rankings", styles['Heading2']))
    ranking_data = [['Rank', 'Student', 'Avg Score', 'Sessions', 'Streak']]
    for i, student in enumerate(student_stats, 1):
        ranking_data.append([
            str(i),
            student['name'],
            f"{student['avg_score']:.1f}",
            str(student['sessions']),
            f"{student['streak']}d"
        ])
    
    ranking_table = Table(ranking_data, colWidths=[0.7*inch, 2.5*inch, 1.3*inch, 1.3*inch, 1*inch])
    ranking_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#103D64')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Highlight top 3
        ('BACKGROUND', (0, 1), (-1, 3), colors.HexColor('#FFF8DC')),
    ]))
    story.append(ranking_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1,  # Center
    )
    story.append(Paragraph(
        "Generated by LearnPulse AI Instructor Assistant • support@learnpulse.ai",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

