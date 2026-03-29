from __future__ import annotations

from pydantic import BaseModel, Field

import typing as t
from datetime import datetime


class Course(BaseModel):
    """Course strucutre."""
    id: int
    shortname: str
    fullname: str


class Assignment(BaseModel):
    """Assignment structure."""
    id: int
    name: str
    course: int
    intro: str
    duedate: t.Optional[datetime] = None
    allowsubmissionsfromdate: t.Optional[datetime] = None


class OnlineTextPlugin(BaseModel):
    type: t.Literal["onlinetext"]
    text: str = ""


class File(BaseModel):
    """File model for Filearea."""
    filename: str
    filesize: int
    fileurl: str
    mimetype: str


class FileArea(BaseModel):
    """Filearea structure for file plugin."""
    area: str
    files: t.List[File]


class FilePlugin(BaseModel):
    type: t.Literal["file"]
    fileareas: t.List[FileArea]


class CommentsPlugin(BaseModel):
    type: t.Literal["comments"]
    name: str
    text: str = ""


Plugin = t.Annotated[
    t.Union[
        OnlineTextPlugin,
        FilePlugin,
        CommentsPlugin
    ],
    Field(discriminator="type")
]


class Submission(BaseModel):
    """Submission structure."""
    id: int
    userid: int
    status: str
    gradingstatus: str
    timecreated: datetime
    timemodified: datetime
    plugins: t.List[Plugin]
