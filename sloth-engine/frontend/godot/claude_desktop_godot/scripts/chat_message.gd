extends PanelContainer
# Standalone reusable message bubble component

enum Role { USER, ASSISTANT }

@export var role : Role = Role.USER
@export var content : String = ""

func _ready() -> void:
	_apply_style()

func _apply_style() -> void:
	var style := StyleBoxFlat.new()
	match role:
		Role.USER:
			style.bg_color = Color(0.165, 0.165, 0.165)
			style.set_corner_radius_all(16)
			style.corner_radius_bottom_right = 4
		Role.ASSISTANT:
			style.bg_color = Color(0, 0, 0, 0)
			style.set_border_width_all(0)
	style.content_margin_left   = 16
	style.content_margin_right  = 16
	style.content_margin_top    = 10
	style.content_margin_bottom = 10
	add_theme_stylebox_override("panel", style)
