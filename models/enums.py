import enum


class VideoStatus(str, enum.Enum):
    pending = "pending"
    downloading = "downloading"
    transcribing = "transcribing"
    ready = "ready"
    failed = "failed"


class ClipCandidateStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"


class ClipStatus(str, enum.Enum):
    queued = "queued"
    cutting = "cutting"
    reframing = "reframing"
    translating = "translating"
    dubbing = "dubbing"
    subtitling = "subtitling"
    rendering = "rendering"
    done = "done"
    failed = "failed"


class JobType(str, enum.Enum):
    download = "download"
    transcribe = "transcribe"
    highlight = "highlight"
    clip = "clip"
    reframe = "reframe"
    translate = "translate"
    dub = "dub"
    subtitle = "subtitle"
    render = "render"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
