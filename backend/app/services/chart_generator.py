"""
Chart generation service using Plotly.
Generates charts for both PDF reports (PNG) and web UI (JSON).
"""
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
from datetime import datetime
import io


class ChartGenerator:
    """Generate charts for reports using Plotly."""

    def __init__(self):
        """Initialize chart generator with default styling."""
        self.color_scheme = {
            'verified': '#4CAF50',      # Green
            'pending': '#FFC107',       # Amber
            'flagged': '#FF9800',       # Orange
            'rejected': '#F44336',      # Red
            'primary': '#2196F3',       # Blue
            'secondary': '#9C27B0'      # Purple
        }

    def generate_verification_status_chart(
        self,
        status_counts: Dict[str, int],
        format: str = 'json'
    ) -> Any:
        """
        Generate pie chart for verification status distribution.
        
        Args:
            status_counts: Dict with status as key and count as value
            format: 'json' for web UI, 'png' for PDF
            
        Returns:
            Chart in requested format
        """
        labels = list(status_counts.keys())
        values = list(status_counts.values())
        colors = [self.color_scheme.get(label.lower(), '#9E9E9E') for label in labels]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='auto',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title={
                'text': 'Verification Status Distribution',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'family': 'Arial, sans-serif'}
            },
            showlegend=True,
            width=800,
            height=500
        )
        
        return self._export_chart(fig, format)

    def generate_confidence_score_histogram(
        self,
        confidence_scores: List[float],
        format: str = 'json'
    ) -> Any:
        """Generate histogram for confidence score distribution."""
        fig = go.Figure(data=[go.Histogram(
            x=confidence_scores,
            nbinsx=20,
            marker=dict(color=self.color_scheme['primary'])
        )])
        
        fig.update_layout(
            title='Confidence Score Distribution',
            xaxis_title='Confidence Score',
            yaxis_title='Number of Photos',
            width=800,
            height=500
        )
        
        return self._export_chart(fig, format)

    def generate_photos_over_time_chart(
        self,
        timestamps: List[datetime],
        format: str = 'json'
    ) -> Any:
        """Generate line chart showing photos captured over time."""
        from collections import Counter
        dates = [ts.date() for ts in timestamps]
        date_counts = Counter(dates)
        
        sorted_dates = sorted(date_counts.keys())
        counts = [date_counts[date] for date in sorted_dates]
        
        fig = go.Figure(data=[go.Scatter(
            x=sorted_dates,
            y=counts,
            mode='lines+markers',
            line=dict(color=self.color_scheme['primary'], width=2)
        )])
        
        fig.update_layout(
            title='Photos Captured Over Time',
            xaxis_title='Date',
            yaxis_title='Number of Photos',
            width=800,
            height=500
        )
        
        return self._export_chart(fig, format)

    def _export_chart(self, fig: go.Figure, format: str) -> Any:
        """Export chart in requested format."""
        if format == 'json':
            return fig.to_json()
        elif format == 'png':
            img_bytes = fig.to_image(format='png', width=800, height=500, scale=2)
            return img_bytes
        elif format == 'html':
            return fig.to_html(include_plotlyjs='cdn', full_html=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
