from pydantic.dataclasses import dataclass

# @dataclass(frozen=True)
# class ParcelTypeInputDTO:
#     name: str


@dataclass(frozen=True)
class ParcelTypeOutputDTO:
    id: int
    name: str
