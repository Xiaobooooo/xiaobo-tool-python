from typing import Optional, Any, Union, get_origin, get_args

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型，由 pydantic-settings 驱动。"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # 环境变量名不区分大小写
        extra='ignore'
    )

    # --- 任务名称（用于解析 Union[bool, str] 类型字段）---
    task_name: Optional[str] = Field(default=None, exclude=True)

    # --- 线程池配置 ---
    max_workers: int = Field(default=5, gt=0, description="最大线程数")

    # --- 代理配置 ---
    proxy: Optional[str] = Field(default=None, description="代理")
    proxy_ipv6: Optional[str] = Field(default=None, description="IPv6代理")
    proxy_api: Optional[str] = Field(default=None, description="代理API地址")
    proxy_ipv6_api: Optional[str] = Field(default=None, description="IPv6代理API地址")

    # --- 任务执行配置 ---
    retries: int = Field(default=2, ge=0, description="重试次数")
    retry_delay: float = Field(default=0.0, ge=0, description="重试延迟（秒）")
    shuffle: Union[bool] = Field(default=False, description="打乱任务顺序")
    use_proxy_ipv6: Union[bool] = Field(default=False, description="使用IPv6代理")
    disable_proxy: Union[bool] = Field(default=False, description="禁用代理")

    @field_validator('*', mode='before')
    @classmethod
    def preprocess_field(cls, v: Any, info: FieldValidationInfo) -> Any:
        """
        预处理字段值：
        1. 空字符串转换为默认值
        2. 对 Union[bool, str] 类型的字段，将常见布尔字符串转为 bool
        """
        field_info = cls.model_fields.get(info.field_name)
        if not field_info:
            return v

        # 空字符串转默认值
        if v == "":
            return field_info.default

        # 检查是否是 Union[bool, str] 类型
        annotation = field_info.annotation
        if get_origin(annotation) is Union:
            args = get_args(annotation)
            if bool in args and str in args:
                if isinstance(v, bool):
                    return v
                if isinstance(v, int):
                    return v != 0
                if isinstance(v, str):
                    lower_v = v.strip().lower()
                    if lower_v in ('true', 'yes', 'y', '1', 'on'):
                        return True
                    if lower_v in ('false', 'no', 'n', '0', 'off'):
                        return False
        return v

    @model_validator(mode='after')
    def resolve_bool_str_fields(self) -> 'Settings':
        """
        根据 task_name 解析 Union[bool, str] 类型字段中的 task1&task2 格式。
        将字符串值转换为布尔值。
        """
        if not self.task_name:
            return self

        for field_name, field_info in self.model_fields.items():
            annotation = field_info.annotation
            if get_origin(annotation) is Union:
                args = get_args(annotation)
                if bool in args and str in args:
                    value = getattr(self, field_name)
                    if isinstance(value, str):
                        names = [n.strip() for n in value.split('&')]
                        object.__setattr__(self, field_name, self.task_name in names)
        return self
