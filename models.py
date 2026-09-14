from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanvasElementType(str, Enum):
    """Supported diagram element types."""

    # Basic
    RECTANGLE = "rectangle"
    ROUNDED_RECTANGLE = "rounded_rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    DIAMOND = "diamond"
    TRIANGLE = "triangle"
    HEXAGON = "hexagon"
    DOUBLE_ELLIPSE = "double_ellipse"
    TEXT = "text"

    # Flowchart
    START_END = "start_end"
    PROCESS = "process"
    DECISION = "decision"
    DOCUMENT = "document"
    DATA = "data"
    SUBPROCESS = "subprocess"

    # Architecture
    IMAGE = "image"
    ACTOR = "actor"
    USER = "user"
    DATABASE = "database"
    CLOUD = "cloud"
    SERVER = "server"
    API = "api"
    SERVICE = "service"
    QUEUE = "queue"
    CONTAINER = "container"
    CODE = "code"

    # UML / ERD
    CLASS = "class"
    ENTITY = "entity"
    TABLE = "table"
    SWIMLANE = "swimlane"

    # Additional UML and business-process notation.
    NOTE = "note"
    USE_CASE = "use_case"
    SYSTEM_BOUNDARY = "system_boundary"
    BPMN_START_EVENT = "bpmn_start_event"
    BPMN_INTERMEDIATE_EVENT = "bpmn_intermediate_event"
    BPMN_END_EVENT = "bpmn_end_event"
    BPMN_TASK = "bpmn_task"
    BPMN_SUBPROCESS = "bpmn_subprocess"
    BPMN_EXCLUSIVE_GATEWAY = "bpmn_exclusive_gateway"
    BPMN_PARALLEL_GATEWAY = "bpmn_parallel_gateway"
    BPMN_INCLUSIVE_GATEWAY = "bpmn_inclusive_gateway"
    POOL = "pool"
    PACKAGE = "package"
    INITIAL_STATE = "initial_state"
    FINAL_STATE = "final_state"
    FORK_JOIN = "fork_join"
    LIFELINE = "lifeline"
    ACTIVATION = "activation"

    # Compatibility with old payloads.
    LINE = "line"
    ARROW = "arrow"


class CanvasLineType(str, Enum):
    """Supported connection routing styles."""

    STRAIGHT = "straight"
    ORTHOGONAL = "orthogonal"
    ELBOW = "elbow"
    SEGMENTED = "segmented"
    CURVED = "curved"


class CanvasArrowType(str, Enum):
    """Supported connection arrow heads."""

    NONE = "none"
    CLASSIC = "classic"
    BLOCK = "block"
    OPEN = "open"
    DIAMOND = "diamond"
    OVAL = "oval"
    CLASSIC_THIN = "classicThin"
    BLOCK_THIN = "blockThin"
    OPEN_THIN = "openThin"
    DIAMOND_THIN = "diamondThin"
    ER_ONE = "erOne"
    ER_MANY = "erMany"
    ER_ZERO_ONE = "erZeroOne"
    ER_ONE_MANY = "erOneMany"
    ER_ZERO_MANY = "erZeroMany"


class CanvasElementStyle(BaseModel):
    """Optional visual overrides for an element."""

    model_config = ConfigDict(extra="forbid")

    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(
        default=None,
        ge=0,
    )
    font_size: float | None = Field(
        default=None,
        gt=0,
    )
    font_color: str | None = None


class CanvasConnectionStyle(BaseModel):
    """Optional visual overrides for a connection."""

    model_config = ConfigDict(extra="forbid")

    line_type: CanvasLineType | None = None
    stroke: str | None = None

    stroke_width: float | None = Field(
        default=None,
        ge=0,
    )

    dashed: bool | None = None

    start_arrow: CanvasArrowType | None = None
    end_arrow: CanvasArrowType | None = None
    start_fill: bool = True
    end_fill: bool = True
    start_size: float = Field(default=10, ge=4, le=40)
    end_size: float = Field(default=10, ge=4, le=40)


class CanvasElement(BaseModel):
    """One editable diagram element."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
    )

    type: CanvasElementType

    x: float = 0
    y: float = 0

    width: float = Field(
        default=160,
        gt=0,
    )

    height: float = Field(
        default=80,
        gt=0,
    )

    # An Iconify id, "collection:name" — e.g. "logos:java", "devicon:docker",
    # "simple-icons:postgresql", "lucide:database". Set it from a
    # search_diagram_icons result; never guess one. The server fetches the SVG
    # and inlines it into image_data, so the browser makes no outbound request.
    icon_id: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$",
        description=(
            "Iconify icon id in 'collection:name' form, taken from a "
            "search_diagram_icons result (for example 'logos:java'). Do not "
            "invent one. Setting it makes this element render as that icon."
        ),
    )
    image_data: str | None = Field(
        default=None,
        max_length=2800000,
        pattern=r"^data:image/(?:png|svg\+xml);base64,[A-Za-z0-9+/=]+$",
    )
    attribution: str | None = Field(default=None, max_length=2000)

    lanes: list[str] | None = Field(default=None, min_length=1, max_length=12)

    rotation: float = 0

    text: str = ""

    style: CanvasElementStyle | None = None


class CanvasConnection(BaseModel):
    """One editable connection between two elements."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
    )

    source: str = Field(
        min_length=1,
    )

    target: str = Field(
        min_length=1,
    )

    label: str | None = None

    style: CanvasConnectionStyle | None = None


class CreateCanvasDiagramBody(BaseModel):
    """Request body for the editable canvas diagram tool."""

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str = Field(
        default="Diagram",
        min_length=1,
        max_length=200,
    )

    elements: list[CanvasElement] = Field(
        default_factory=list,
    )

    connections: list[CanvasConnection] = Field(
        default_factory=list,
    )

    @model_validator(
        mode="after",
    )
    def validate_graph(
        self,
    ) -> "CreateCanvasDiagramBody":
        """Validate IDs and connection references."""

        element_ids = [
            element.id
            for element
            in self.elements
        ]

        connection_ids = [
            connection.id
            for connection
            in self.connections
        ]

        if len(
            element_ids
        ) != len(
            set(
                element_ids
            )
        ):
            raise ValueError(
                "Element IDs must be unique"
            )

        if len(
            connection_ids
        ) != len(
            set(
                connection_ids
            )
        ):
            raise ValueError(
                "Connection IDs must be unique"
            )

        known_elements = set(
            element_ids
        )

        for connection in self.connections:

            if connection.source not in known_elements:
                raise ValueError(
                    f"Unknown connection source: "
                    f"{connection.source}"
                )

            if connection.target not in known_elements:
                raise ValueError(
                    f"Unknown connection target: "
                    f"{connection.target}"
                )

            if connection.source == connection.target:
                raise ValueError(
                    "A connection cannot target its own source"
                )

        return self