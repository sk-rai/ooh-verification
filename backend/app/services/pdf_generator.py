"""
PDF report generation service.
Generates comprehensive campaign reports with statistics, charts, and maps.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image as RLImage
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFGenerator:
    """Generate PDF reports for campaigns."""

    def __init__(self):
        """Initialize PDF generator."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is not installed. Install it with: pip install reportlab"
            )
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2196F3'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976D2'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.grey
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatValue',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        ))

    def generate_campaign_report(
        self,
        campaign_data: Dict[str, Any],
        statistics: Dict[str, Any],
        chart_images: Dict[str, bytes],
        output_path: Optional[str] = None
    ) -> bytes:
        """
        Generate comprehensive PDF report for a campaign.
        
        Args:
            campaign_data: Campaign information
            statistics: Campaign statistics
            chart_images: Dict of chart_type -> PNG image bytes
            output_path: Optional file path to save PDF
            
        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        
        # Title Page
        story.extend(self._create_title_page(campaign_data))
        story.append(PageBreak())
        
        # Executive Summary
        story.extend(self._create_executive_summary(campaign_data, statistics))
        story.append(Spacer(1, 0.3 * inch))
        
        # Statistics Section
        story.extend(self._create_statistics_section(statistics))
        story.append(Spacer(1, 0.3 * inch))
        
        # Charts Section
        if chart_images:
            story.extend(self._create_charts_section(chart_images))
        
        # Build PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes

    def _create_title_page(self, campaign_data: Dict[str, Any]) -> List:
        """Create title page elements."""
        elements = []
        
        # Add spacing from top
        elements.append(Spacer(1, 2 * inch))
        
        # Title
        title = Paragraph(
            f"Campaign Report<br/>{campaign_data.get('name', 'Unknown Campaign')}",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 0.5 * inch))
        
        # Campaign details table
        details_data = [
            ['Campaign Code:', campaign_data.get('code', 'N/A')],
            ['Campaign Type:', campaign_data.get('type', 'N/A').replace('_', ' ').title()],
            ['Status:', campaign_data.get('status', 'N/A').title()],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        details_table = Table(details_data, colWidths=[2 * inch, 3 * inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        elements.append(details_table)
        
        return elements

    def _create_executive_summary(
        self,
        campaign_data: Dict[str, Any],
        statistics: Dict[str, Any]
    ) -> List:
        """Create executive summary section."""
        elements = []
        
        elements.append(Paragraph('Executive Summary', self.styles['SectionHeader']))
        
        stats = statistics.get('statistics', {})
        total_photos = stats.get('total_photos', 0)
        avg_confidence = stats.get('average_confidence', 0)
        flagged_photos = stats.get('flagged_photos', 0)
        
        summary_text = f"""
        This report provides a comprehensive overview of the campaign 
        <b>{campaign_data.get('name', 'Unknown')}</b>. 
        A total of <b>{total_photos}</b> photos were captured with an average 
        confidence score of <b>{avg_confidence}%</b>. 
        {f'<b>{flagged_photos}</b> photos were flagged for review.' if flagged_photos > 0 else 'No photos were flagged for review.'}
        """
        
        elements.append(Paragraph(summary_text, self.styles['Normal']))
        
        return elements

    def _create_statistics_section(self, statistics: Dict[str, Any]) -> List:
        """Create statistics section with key metrics."""
        elements = []
        
        elements.append(Paragraph('Campaign Statistics', self.styles['SectionHeader']))
        
        stats = statistics.get('statistics', {})
        
        # Key metrics table
        metrics_data = [
            ['Metric', 'Value'],
            ['Total Photos', str(stats.get('total_photos', 0))],
            ['Average Confidence Score', f"{stats.get('average_confidence', 0)}%"],
            ['Flagged Photos', str(stats.get('flagged_photos', 0))],
        ]
        
        # Add status counts
        status_counts = stats.get('status_counts', {})
        for status, count in status_counts.items():
            metrics_data.append([f'{status.title()} Photos', str(count)])
        
        metrics_table = Table(metrics_data, colWidths=[3 * inch, 2 * inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(metrics_table)
        
        # Vendor performance
        vendor_counts = stats.get('vendor_counts', {})
        if vendor_counts:
            elements.append(Spacer(1, 0.3 * inch))
            elements.append(Paragraph('Vendor Performance', self.styles['SectionHeader']))
            
            vendor_data = [['Vendor ID', 'Photos Captured']]
            for vendor_id, count in sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True):
                vendor_data.append([vendor_id, str(count)])
            
            vendor_table = Table(vendor_data, colWidths=[2 * inch, 2 * inch])
            vendor_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            elements.append(vendor_table)
        
        return elements

    def _create_charts_section(self, chart_images: Dict[str, bytes]) -> List:
        """Create charts section with embedded images."""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph('Visual Analytics', self.styles['SectionHeader']))
        
        chart_titles = {
            'verification': 'Verification Status Distribution',
            'confidence': 'Confidence Score Distribution',
            'timeline': 'Photos Captured Over Time'
        }
        
        for chart_type, image_bytes in chart_images.items():
            if image_bytes:
                elements.append(Spacer(1, 0.2 * inch))
                elements.append(Paragraph(
                    chart_titles.get(chart_type, chart_type.title()),
                    self.styles['Heading3']
                ))
                
                try:
                    img = RLImage(BytesIO(image_bytes), width=5 * inch, height=3 * inch)
                    elements.append(img)
                    elements.append(Spacer(1, 0.3 * inch))
                except Exception as e:
                    elements.append(Paragraph(
                        f"Error loading chart: {str(e)}",
                        self.styles['Normal']
                    ))
        
        return elements
