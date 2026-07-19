# === TASK:WP-305:START ===
"""Strict Tool Schema Registry for WP-305.

Defines parameters, required fields, descriptions and validators.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_specialty_list": {
        "name": "get_specialty_list",
        "description": "Lấy danh sách các chuyên khoa y tế có sẵn trong bệnh viện.",
        "parameters": {
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "Lọc chỉ các chuyên khoa đang hoạt động. Mặc định là True."
                }
            }
        }
    },
    "get_doctor_list": {
        "name": "get_doctor_list",
        "description": "Lấy danh sách bác sĩ, tùy chọn lọc theo chuyên khoa.",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty_id": {
                    "type": "string",
                    "description": "ID chuyên khoa để lọc danh sách bác sĩ."
                },
                "active_only": {
                    "type": "boolean",
                    "description": "Lọc chỉ các bác sĩ đang hoạt động. Mặc định là True."
                }
            }
        }
    },
    "get_available_slots": {
        "name": "get_available_slots",
        "description": "Lấy danh sách các khung giờ khám còn trống của một bác sĩ.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {
                    "type": "string",
                    "description": "ID của bác sĩ cần lấy lịch trống."
                },
                "date_from": {
                    "type": "string",
                    "description": "Ngày bắt đầu tìm kiếm (định dạng YYYY-MM-DD)."
                },
                "date_to": {
                    "type": "string",
                    "description": "Ngày kết thúc tìm kiếm (định dạng YYYY-MM-DD)."
                }
            },
            "required": ["doctor_id"]
        }
    },
    "create_appointment": {
        "name": "create_appointment",
        "description": "Tạo lịch khám bệnh mới. Chỉ gọi sau khi bệnh nhân đã xác nhận thông tin.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {
                    "type": "string",
                    "description": "ID của bác sĩ."
                },
                "slot_id": {
                    "type": "string",
                    "description": "ID của khung giờ khám."
                },
                "patient_name": {
                    "type": "string",
                    "description": "Họ và tên bệnh nhân."
                },
                "patient_phone": {
                    "type": "string",
                    "description": "Số điện thoại liên lạc."
                },
                "patient_dob": {
                    "type": "string",
                    "description": "Ngày sinh bệnh nhân (định dạng YYYY-MM-DD)."
                },
                "has_insurance": {
                    "type": "boolean",
                    "description": "Bệnh nhân có bảo hiểm y tế hay không."
                },
                "visit_reason": {
                    "type": "string",
                    "description": "Lý do đến khám."
                },
                "visit_type": {
                    "type": "string",
                    "description": "Loại khám ('first_visit' hoặc 'follow_up')."
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "Mã xác nhận bảo mật được cấp bởi hệ thống."
                },
                "idempotency_key": {
                    "type": "string",
                    "description": "Mã duy nhất để đảm bảo yêu cầu không bị xử lý lặp lại."
                }
            },
            "required": [
                "doctor_id", "slot_id", "patient_name", "patient_phone",
                "patient_dob", "visit_reason", "visit_type", "confirmation_token"
            ]
        }
    },
    "lookup_appointment": {
        "name": "lookup_appointment",
        "description": "Tra cứu thông tin lịch khám dựa trên mã lịch hẹn.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "Mã lịch hẹn cần tra cứu."
                }
            },
            "required": ["appointment_id"]
        }
    }
}

def validate_tool_input(tool_name: str, arguments: Dict[str, Any]) -> None:
    """Validate tool arguments against registration schema (4.1)."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Tool {tool_name} is not registered.")
    
    schema = TOOL_REGISTRY[tool_name]["parameters"]
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    # Check required fields
    for field in required:
        if field not in arguments or arguments[field] is None or str(arguments[field]).strip() == "":
            raise ValueError(f"Missing required parameter '{field}' for tool '{tool_name}'")
            
    # Check types
    for key, val in arguments.items():
        if key in properties and val is not None:
            expected_type = properties[key]["type"]
            if expected_type == "boolean" and not isinstance(val, bool):
                raise TypeError(f"Parameter '{key}' for tool '{tool_name}' must be boolean")
            elif expected_type == "string" and not isinstance(val, str):
                raise TypeError(f"Parameter '{key}' for tool '{tool_name}' must be string")
# === TASK:WP-305:END ===
