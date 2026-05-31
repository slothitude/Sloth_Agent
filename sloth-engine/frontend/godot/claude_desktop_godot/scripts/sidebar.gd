extends VBoxContainer
# Sidebar controller — handles search filtering, active state

@onready var search_box       : LineEdit     = $SidebarHeader/SearchMargin/SearchBox
@onready var conv_list        : VBoxContainer = $HistoryMargin/HistoryScroll/ConversationList
@onready var history_separator: Label         = $HistorySeparatorLabel

func _ready() -> void:
	_style_search_box()
	_style_separator()
	if search_box:
		search_box.text_changed.connect(_on_search_changed)

func _style_search_box() -> void:
	if not search_box:
		return
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.13, 0.13, 0.13)
	style.border_color = Color(0.22, 0.22, 0.22)
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	style.content_margin_left   = 10
	style.content_margin_right  = 10
	style.content_margin_top    = 6
	style.content_margin_bottom = 6
	search_box.add_theme_stylebox_override("normal", style)
	search_box.add_theme_stylebox_override("focus",  style)

func _style_separator() -> void:
	if not history_separator:
		return
	var margin := MarginContainer.new()
	history_separator.add_theme_constant_override("margin_left", 16)
	history_separator.add_theme_constant_override("margin_top", 12)
	history_separator.add_theme_constant_override("margin_bottom", 4)

func _on_search_changed(new_text: String) -> void:
	if not conv_list:
		return
	var query := new_text.to_lower().strip_edges()
	for child in conv_list.get_children():
		if child is MarginContainer:
			var btn := child.get_child(0) as Button
			if btn:
				child.visible = query.is_empty() or btn.text.to_lower().contains(query)
