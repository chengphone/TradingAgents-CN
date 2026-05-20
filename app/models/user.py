"""用户数据模型（微信小程序版 - 最小化）"""

from typing import Any, Annotated
from pydantic import BeforeValidator, PlainSerializer


def validate_user_id(v: Any) -> str:
    if isinstance(v, str):
        return v
    raise ValueError(f"Invalid user ID, expected string: {type(v)}")


PyObjectId = Annotated[
    str,
    BeforeValidator(validate_user_id),
    PlainSerializer(str, return_type=str),
]
