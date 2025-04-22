from typing import TypedDict, Optional, Annotated, Union
from os import PathLike

diff = Annotated[str, "diff"]
FilePath = Union[str, "PathLike[str]"]
