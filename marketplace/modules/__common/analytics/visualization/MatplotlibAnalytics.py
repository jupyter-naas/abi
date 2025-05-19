from abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import matplotlib.pyplot as plt
import numpy as np
import random
from typing import List, Optional, Tuple, Dict, Union
from abi import logger
from wordcloud import WordCloud

LOGO_URL = "https://logo.clearbit.com/matplotlib.org"


@dataclass
class MatplotlibAnalyticsConfiguration(IntegrationConfiguration):
    """Configuration for Matplotlib Analytics.

    Attributes:
        figsize (tuple): Default figure size (width, height)
        dpi (int): Dots per inch for figure resolution
        style (str): Matplotlib style to use
        title_fontsize (int): Font size for titles
        label_fontsize (int): Font size for axis labels
        tick_fontsize (int): Font size for tick labels
    """

    figsize: Tuple[int, int] = (10, 6)
    dpi: int = 100
    style: str = "default"
    title_fontsize: int = 14
    label_fontsize: int = 12
    tick_fontsize: int = 10


class MatplotlibAnalytics(Integration):
    """Generate data visualizations using Matplotlib."""

    __configuration: MatplotlibAnalyticsConfiguration

    def __init__(self, configuration: MatplotlibAnalyticsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def __apply_style(self):
        """Apply configured style settings to matplotlib plots."""
        plt.style.use(self.__configuration.style)
        plt.rcParams["figure.figsize"] = self.__configuration.figsize
        plt.rcParams["figure.dpi"] = self.__configuration.dpi
        plt.rcParams["font.size"] = self.__configuration.label_fontsize
        plt.rcParams["axes.titlesize"] = self.__configuration.title_fontsize
        plt.rcParams["axes.labelsize"] = self.__configuration.label_fontsize
        plt.rcParams["xtick.labelsize"] = self.__configuration.tick_fontsize
        plt.rcParams["ytick.labelsize"] = self.__configuration.tick_fontsize

    def __save_figure(self, filename: str) -> str:
        """Save the current figure to a file.

        Args:
            filename (str): Name of the file to save (without extension)

        Returns:
            str: Path to the saved file
        """
        from pathlib import Path

        # Format filename
        filename = filename.replace(" ", "_").lower()

        # Create analytics directory if it doesn't exist
        save_dir = Path("src/data/analytics")
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save figure
        filepath = save_dir / f"{filename}.png"
        plt.savefig(filepath, dpi=self.__configuration.dpi, bbox_inches="tight")
        plt.close()

        logger.info(f"Saved figure to {filepath}")
        return str(filepath)

    def create_line_chart(
        self,
        x_data: Optional[List] = None,
        y_data: Optional[List] = None,
        title: str = "Line Chart",
        xlabel: str = "X Axis",
        ylabel: str = "Y Axis",
    ) -> str:
        """Create a line chart visualization."""
        if x_data is None or y_data is None:
            x_data = list(range(10))
            y_data = [random.randint(0, 100) for _ in range(10)]

        self.__apply_style()
        plt.figure()
        plt.plot(x_data, y_data, marker="o")
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_bar_chart(
        self,
        x_data: Optional[List] = None,
        y_data: Optional[List] = None,
        title: str = "Bar Chart",
        xlabel: str = "Categories",
        ylabel: str = "Values",
    ) -> str:
        """Create a bar chart visualization."""
        if x_data is None or y_data is None:
            x_data = [f"Category {i}" for i in range(5)]
            y_data = [random.randint(0, 100) for _ in range(5)]

        self.__apply_style()
        plt.figure()
        plt.bar(x_data, y_data)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_scatter_plot(
        self,
        x_data: Optional[List] = None,
        y_data: Optional[List] = None,
        title: str = "Scatter Plot",
        xlabel: str = "X Values",
        ylabel: str = "Y Values",
    ) -> str:
        """Create a scatter plot visualization."""
        if x_data is None or y_data is None:
            x_data = [random.uniform(0, 100) for _ in range(50)]
            y_data = [random.uniform(0, 100) for _ in range(50)]

        self.__apply_style()
        plt.figure()
        plt.scatter(x_data, y_data, alpha=0.6)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_pie_chart(
        self,
        values: Optional[List] = None,
        labels: Optional[List] = None,
        title: str = "Pie Chart",
    ) -> str:
        """Create a pie chart visualization."""
        if values is None or labels is None:
            values = [random.randint(10, 100) for _ in range(5)]
            labels = [f"Category {i}" for i in range(5)]

        self.__apply_style()
        plt.figure()
        plt.pie(values, labels=labels, autopct="%1.1f%%")
        plt.title(title)

        return self.__save_figure(title)

    def create_histogram(
        self,
        data: Optional[List] = None,
        bins: int = 30,
        title: str = "Histogram",
        xlabel: str = "Values",
        ylabel: str = "Frequency",
    ) -> str:
        """Create a histogram visualization."""
        if data is None:
            data = [random.gauss(0, 1) for _ in range(1000)]

        self.__apply_style()
        plt.figure()
        plt.hist(data, bins=bins, edgecolor="black")
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_box_plot(
        self,
        data: Optional[List[List]] = None,
        labels: Optional[List] = None,
        title: str = "Box Plot",
        xlabel: str = "Categories",
        ylabel: str = "Values",
    ) -> str:
        """Create a box plot visualization."""
        if data is None:
            data = [[random.gauss(0, 1) for _ in range(100)] for _ in range(4)]
            labels = [f"Group {i}" for i in range(4)]

        self.__apply_style()
        plt.figure()
        plt.boxplot(data, labels=labels)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_heatmap(
        self,
        data: Optional[List[List]] = None,
        title: str = "Heatmap",
        xlabel: str = "X Axis",
        ylabel: str = "Y Axis",
    ) -> str:
        """Create a heatmap visualization."""
        if data is None:
            data = [[random.uniform(0, 1) for _ in range(10)] for _ in range(10)]

        self.__apply_style()
        plt.figure()
        plt.imshow(data, cmap="YlOrRd")
        plt.colorbar()

        # Add text annotations
        for i in range(len(data)):
            for j in range(len(data[i])):
                plt.text(j, i, f"{data[i][j]:.2f}", ha="center", va="center")

        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_stacked_bar(
        self,
        data: Optional[List[List]] = None,
        categories: Optional[List] = None,
        labels: Optional[List] = None,
        title: str = "Stacked Bar Chart",
        xlabel: str = "Categories",
        ylabel: str = "Values",
    ) -> str:
        """Create a stacked bar chart visualization."""
        if data is None:
            data = [[random.randint(1, 20) for _ in range(4)] for _ in range(3)]
            categories = [f"Category {i}" for i in range(4)]
            labels = [f"Series {i}" for i in range(3)]

        self.__apply_style()
        plt.figure()
        bottom = np.zeros(len(categories))

        for i, row in enumerate(data):
            plt.bar(categories, row, bottom=bottom, label=labels[i])
            bottom += row

        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.legend()

        return self.__save_figure(title)

    def create_violin_plot(
        self,
        data: Optional[List[List]] = None,
        labels: Optional[List] = None,
        title: str = "Violin Plot",
        xlabel: str = "Categories",
        ylabel: str = "Distribution",
    ) -> str:
        """Create a violin plot visualization."""
        if data is None:
            data = [np.random.normal(loc=i, scale=1, size=100) for i in range(4)]
            labels = [f"Group {i}" for i in range(4)]

        self.__apply_style()
        plt.figure()
        plt.violinplot(data)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.xticks(range(1, len(labels) + 1), labels)

        return self.__save_figure(title)

    def create_area_chart(
        self,
        x_data: Optional[List] = None,
        y_data: Optional[List] = None,
        title: str = "Area Chart",
        xlabel: str = "X Axis",
        ylabel: str = "Y Axis",
    ) -> str:
        """Create an area chart visualization."""
        if x_data is None or y_data is None:
            x_data = list(range(10))
            y_data = [random.randint(10, 100) for _ in range(10)]

        self.__apply_style()
        plt.figure()
        plt.fill_between(x_data, y_data, alpha=0.5)
        plt.plot(x_data, y_data)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)

        return self.__save_figure(title)

    def create_wordcloud(
        self,
        text: Union[str, Dict[str, float], List[str]],
        title: str = "Word Cloud",
        width: int = 800,
        height: int = 400,
        background_color: str = "white",
    ) -> str:
        """Create a word cloud visualization.

        Args:
            text (Union[str, Dict[str, float], List[str]]): Text to generate word cloud from,
                dictionary of word frequencies, or list of words
            title (str): Title for the visualization
            width (int): Width of the word cloud image
            height (int): Height of the word cloud image
            background_color (str): Background color of the word cloud

        Returns:
            str: Path to the saved word cloud image
        """
        if text is None:
            # Generate sample text if none provided
            words = [
                "Python",
                "Data_Analytics",
                "Data_Visualization",
                "Cloud_Computing",
                "Machine_Learning",
                "AI",
                "Graph_Database",
                "Neural_Network",
                "Clean_Code",
            ]
            text = " ".join([word * random.randint(1, 5) for word in words])
        elif isinstance(text, list):
            # Group multi-word phrases with underscores and join with repetition for weighting
            processed_words = []
            for word in text:
                # Replace spaces with underscores to keep phrases together
                processed_word = word.replace(" ", "_")
                processed_words.append(processed_word * random.randint(1, 5))
            text = " ".join(processed_words)

        self.__apply_style()
        plt.figure()

        # Create word cloud with common parameters
        wordcloud_params = {
            "width": width,
            "height": height,
            "background_color": background_color,
            "collocations": False,
            "max_words": 200,
            # Commented this max_font_size as it is set to None later on and don't know the side effect.
            # I am assuming that python will take the later value.
            # "max_font_size": 40,
            "min_font_size": 10,
            "prefer_horizontal": 0.9,
            "scale": 2,
            "relative_scaling": 0.5,
            "stopwords": None,
            "random_state": 42,
            "font_path": None,
            "max_font_size": None,
        }

        # Generate word cloud based on input type
        wordcloud = WordCloud(**wordcloud_params).generate(text)
        # Display the word cloud
        plt.imshow(wordcloud, interpolation="bilinear")
        plt.axis("off")

        return self.__save_figure(title)


def as_tools(configuration: MatplotlibAnalyticsConfiguration):
    """Convert Matplotlib Analytics into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional, List

    class BasicChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis")
        title: str = Field(default="Chart", description="Chart title")
        xlabel: str = Field(default="X Axis", description="X-axis label")
        ylabel: str = Field(default="Y Axis", description="Y-axis label")

    class PieChartSchema(BaseModel):
        values: Optional[List] = Field(
            default=None, description="Values for pie slices"
        )
        labels: Optional[List] = Field(
            default=None, description="Labels for pie slices"
        )
        title: str = Field(default="Pie Chart", description="Chart title")

    class HistogramSchema(BaseModel):
        data: Optional[List] = Field(default=None, description="Data to plot")
        bins: int = Field(default=30, description="Number of bins")
        title: str = Field(default="Histogram", description="Chart title")
        xlabel: str = Field(default="Values", description="X-axis label")
        ylabel: str = Field(default="Frequency", description="Y-axis label")

    class BoxPlotSchema(BaseModel):
        data: Optional[List[List]] = Field(
            default=None, description="List of data arrays to plot"
        )
        labels: Optional[List] = Field(default=None, description="Labels for each box")
        title: str = Field(default="Box Plot", description="Chart title")
        xlabel: str = Field(default="Categories", description="X-axis label")
        ylabel: str = Field(default="Values", description="Y-axis label")

    class HeatmapSchema(BaseModel):
        data: Optional[List[List]] = Field(
            default=None, description="2D array of values for heatmap"
        )
        title: str = Field(default="Heatmap", description="Chart title")
        xlabel: str = Field(default="X Axis", description="X-axis label")
        ylabel: str = Field(default="Y Axis", description="Y-axis label")

    class StackedBarSchema(BaseModel):
        data: Optional[List[List]] = Field(
            default=None, description="List of data arrays for each stack"
        )
        categories: Optional[List] = Field(default=None, description="Category labels")
        labels: Optional[List] = Field(
            default=None, description="Labels for each stack"
        )
        title: str = Field(default="Stacked Bar Chart", description="Chart title")
        xlabel: str = Field(default="Categories", description="X-axis label")
        ylabel: str = Field(default="Values", description="Y-axis label")

    class ViolinPlotSchema(BaseModel):
        data: Optional[List[List]] = Field(
            default=None, description="List of data arrays to plot"
        )
        labels: Optional[List] = Field(
            default=None, description="Labels for each violin"
        )
        title: str = Field(default="Violin Plot", description="Chart title")
        xlabel: str = Field(default="Categories", description="X-axis label")
        ylabel: str = Field(default="Distribution", description="Y-axis label")

    class WordCloudSchema(BaseModel):
        text: str = Field(
            default="Sample text", description="Text to generate word cloud from"
        )
        title: str = Field(default="Word Cloud", description="Chart title")
        width: int = Field(default=800, description="Width of the word cloud image")
        height: int = Field(default=400, description="Height of the word cloud image")
        background_color: str = Field(
            default="white", description="Background color of the word cloud"
        )

    analytics = MatplotlibAnalytics(configuration)

    return [
        StructuredTool(
            name="matplotlib_line_chart",
            description="Create a line chart visualization. Perfect for showing trends over time.",
            func=lambda **kwargs: analytics.create_line_chart(**kwargs),
            args_schema=BasicChartSchema,
        ),
        StructuredTool(
            name="matplotlib_bar_chart",
            description="Create a bar chart visualization. Ideal for comparing categories.",
            func=lambda **kwargs: analytics.create_bar_chart(**kwargs),
            args_schema=BasicChartSchema,
        ),
        StructuredTool(
            name="matplotlib_scatter_plot",
            description="Create a scatter plot visualization. Great for showing relationships between variables.",
            func=lambda **kwargs: analytics.create_scatter_plot(**kwargs),
            args_schema=BasicChartSchema,
        ),
        StructuredTool(
            name="matplotlib_pie_chart",
            description="Create a pie chart visualization. Perfect for showing proportions of a whole.",
            func=lambda **kwargs: analytics.create_pie_chart(**kwargs),
            args_schema=PieChartSchema,
        ),
        StructuredTool(
            name="matplotlib_histogram",
            description="Create a histogram visualization. Ideal for showing distribution of data.",
            func=lambda **kwargs: analytics.create_histogram(**kwargs),
            args_schema=HistogramSchema,
        ),
        StructuredTool(
            name="matplotlib_box_plot",
            description="Create a box plot visualization. Shows distribution statistics with quartiles and outliers.",
            func=lambda **kwargs: analytics.create_box_plot(**kwargs),
            args_schema=BoxPlotSchema,
        ),
        StructuredTool(
            name="matplotlib_heatmap",
            description="Create a heatmap visualization. Perfect for showing patterns in 2D data.",
            func=lambda **kwargs: analytics.create_heatmap(**kwargs),
            args_schema=HeatmapSchema,
        ),
        StructuredTool(
            name="matplotlib_stacked_bar",
            description="Create a stacked bar chart visualization. Shows composition of categories.",
            func=lambda **kwargs: analytics.create_stacked_bar(**kwargs),
            args_schema=StackedBarSchema,
        ),
        StructuredTool(
            name="matplotlib_violin_plot",
            description="Create a violin plot visualization. Shows probability density of data.",
            func=lambda **kwargs: analytics.create_violin_plot(**kwargs),
            args_schema=ViolinPlotSchema,
        ),
        StructuredTool(
            name="matplotlib_area_chart",
            description="Create an area chart visualization. Shows cumulative totals over time.",
            func=lambda **kwargs: analytics.create_area_chart(**kwargs),
            args_schema=BasicChartSchema,
        ),
        StructuredTool(
            name="matplotlib_wordcloud",
            description="Create a word cloud visualization. Ideal for showing word frequencies.",
            func=lambda **kwargs: analytics.create_wordcloud(**kwargs),
            args_schema=WordCloudSchema,
        ),
    ]
