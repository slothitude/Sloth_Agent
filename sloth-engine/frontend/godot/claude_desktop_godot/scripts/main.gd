extends Control

# ─── Claude Desktop Color Palette ───────────────────────────────────────────
const C_BG             := Color(0.102, 0.102, 0.102)   # #1a1a1a
const C_SIDEBAR        := Color(0.090, 0.090, 0.090)   # #171717
const C_SURFACE        := Color(0.130, 0.130, 0.130)   # #212121
const C_SURFACE_RAISED := Color(0.165, 0.165, 0.165)   # #2a2a2a
const C_BORDER         := Color(0.200, 0.200, 0.200)   # #333333
const C_ACCENT         := Color(0.855, 0.467, 0.337)   # #da7756  Claude orange
const C_TEXT_PRIMARY   := Color(0.925, 0.925, 0.925)   # #ececec
const C_TEXT_SECONDARY := Color(0.608, 0.608, 0.608)   # #9b9b9b
const C_TEXT_MUTED     := Color(0.420, 0.420, 0.420)   # #6b6b6b
const C_USER_BUBBLE    := Color(0.165, 0.165, 0.165)   # user message bg
const C_SEND_BTN       := Color(0.855, 0.467, 0.337)   # accent

# ─── API Configuration ────────────────────────────────────────────────────
var api_base: String = ""
var auth_token: String = "sloth-engine-admin-token"

# ─── Node References ────────────────────────────────────────────────────────
@onready var message_list        : VBoxContainer  = $AppLayout/ChatArea/MessageScrollContainer/MessageList
@onready var scroll_container    : ScrollContainer= $AppLayout/ChatArea/MessageScrollContainer
@onready var message_input       : TextEdit       = $AppLayout/ChatArea/InputArea/InputMargin/InputBox/InputBoxInner/TextInputMargin/MessageInput
@onready var send_btn            : Button         = $AppLayout/ChatArea/InputArea/InputMargin/InputBox/InputBoxInner/InputToolbar/ToolbarMargin/ToolbarHBox/SendBtn
@onready var conversation_list   : VBoxContainer  = $AppLayout/Sidebar/SidebarContent/HistoryMargin/HistoryScroll/ConversationList
@onready var welcome_screen      : CenterContainer= $AppLayout/ChatArea/MessageScrollContainer/MessageList/WelcomeScreen
@onready var suggestions_grid    : GridContainer  = $AppLayout/ChatArea/MessageScrollContainer/MessageList/WelcomeScreen/WelcomeVBox/SuggestionsGrid
@onready var input_box           : PanelContainer = $AppLayout/ChatArea/InputArea/InputMargin/InputBox
@onready var claude_logo_ctrl    : Control        = $AppLayout/Sidebar/SidebarContent/SidebarHeader/LogoRow/MarginContainer/LogoHBox/ClaudeLogo
@onready var welcome_logo_ctrl   : Control        = $AppLayout/ChatArea/MessageScrollContainer/MessageList/WelcomeScreen/WelcomeVBox/WelcomeLogo
@onready var model_dot           : Control        = $AppLayout/ChatArea/TopBar/TopBarMargin/TopBarInner/ModelSelector/ModelDot
@onready var model_name          : Label          = $AppLayout/ChatArea/TopBar/TopBarMargin/TopBarInner/ModelSelector/ModelName
@onready var avatar_ctrl         : Control        = $AppLayout/Sidebar/SidebarContent/SidebarFooter/ProfileRow/ProfileMargin/ProfileHBox/Avatar
@onready var attach_btn          : Button         = $AppLayout/ChatArea/InputArea/InputMargin/InputBox/InputBoxInner/InputToolbar/ToolbarMargin/ToolbarHBox/AttachBtn
@onready var footer_note         : Label          = $AppLayout/ChatArea/InputArea/FooterNote
@onready var welcome_title       : Label          = $AppLayout/ChatArea/MessageScrollContainer/MessageList/WelcomeScreen/WelcomeVBox/WelcomeTitle
@onready var model_chip_label    : Label          = $AppLayout/ChatArea/InputArea/InputMargin/InputBox/InputBoxInner/InputToolbar/ToolbarMargin/ToolbarHBox/ModelChip/ModelChipLabel

# ─── Suggestion prompts ─────────────────────────────────────────────────────
const SUGGESTIONS := [
	["Search the web", "for the latest Python news"],
	["List my vault skills", "and show me what's available"],
	["Check the weather", "in Cairns, Australia right now"],
	["Help me debug", "a Python script I'm working on"],
]

# ─── State ─────────────────────────────────────────────────────────────────
var _is_typing := false
var _current_response_label : RichTextLabel
var _typing_dots_timer : Timer
var _dot_count := 0
var _current_chat_id: String = ""
var _new_chat_btn: Button

# ─── Lifecycle ──────────────────────────────────────────────────────────────
func _ready() -> void:
	# Auto-detect API base: browser origin for web export, localhost for desktop
	if OS.has_feature("web"):
		var origin = JavaScriptBridge.eval("window.location.origin")
		api_base = str(origin) if origin != null else "http://localhost:3001"
	else:
		api_base = "http://localhost:3001"
	_apply_input_box_style()
	_build_send_button_style()
	_build_suggestion_cards()
	_setup_signals()
	_setup_typing_dots()
	_update_greeting()
	_update_model_label()
	message_input.grab_focus()

	# Load conversations from API
	_load_conversations()

func _draw() -> void:
	pass

# ─── Dynamic UI updates ────────────────────────────────────────────────────
func _update_greeting() -> void:
	if not welcome_title:
		return
	var hour = Time.get_time_dict_from_system().get("hour", 12)
	var greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
	welcome_title.text = greeting + ", Aaron"

func _update_model_label() -> void:
	if model_name:
		model_name.text = "GLM-5.1"
	if model_chip_label:
		model_chip_label.text = "GLM-5.1"

# ─── Style helpers ──────────────────────────────────────────────────────────
func _apply_input_box_style() -> void:
	var style := StyleBoxFlat.new()
	style.bg_color        = Color(0.13, 0.13, 0.13)
	style.border_color    = C_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(12)
	style.content_margin_left   = 0
	style.content_margin_right  = 0
	style.content_margin_top    = 0
	style.content_margin_bottom = 0
	input_box.add_theme_stylebox_override("panel", style)

	var te_style := StyleBoxFlat.new()
	te_style.bg_color = Color(0, 0, 0, 0)
	te_style.set_border_width_all(0)
	te_style.set_corner_radius_all(0)
	message_input.add_theme_stylebox_override("normal", te_style)
	message_input.add_theme_stylebox_override("focus", te_style)
	message_input.add_theme_color_override("background_color", Color(0, 0, 0, 0))
	message_input.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY

func _build_send_button_style() -> void:
	var normal := StyleBoxFlat.new()
	normal.bg_color = C_ACCENT
	normal.set_corner_radius_all(8)
	normal.content_margin_left   = 8
	normal.content_margin_right  = 8
	normal.content_margin_top    = 4
	normal.content_margin_bottom = 4
	send_btn.add_theme_stylebox_override("normal", normal)

	var hover := StyleBoxFlat.new()
	hover.bg_color = Color(0.92, 0.52, 0.38)
	hover.set_corner_radius_all(8)
	hover.content_margin_left   = 8
	hover.content_margin_right  = 8
	hover.content_margin_top    = 4
	hover.content_margin_bottom = 4
	send_btn.add_theme_stylebox_override("hover", hover)

	var pressed := StyleBoxFlat.new()
	pressed.bg_color = Color(0.76, 0.40, 0.28)
	pressed.set_corner_radius_all(8)
	pressed.content_margin_left   = 8
	pressed.content_margin_right  = 8
	pressed.content_margin_top    = 4
	pressed.content_margin_bottom = 4
	send_btn.add_theme_stylebox_override("pressed", pressed)

# ─── Signals ────────────────────────────────────────────────────────────────
func _setup_signals() -> void:
	send_btn.pressed.connect(_on_send_pressed)
	message_input.gui_input.connect(_on_input_key)
	# New chat button
	_new_chat_btn = $AppLayout/Sidebar/SidebarContent/SidebarHeader/NewChatBtn
	if _new_chat_btn:
		_new_chat_btn.pressed.connect(_on_new_chat)

func _on_input_key(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ENTER and not event.shift_pressed:
			_on_send_pressed()
			get_viewport().set_input_as_handled()

func _on_send_pressed() -> void:
	var text := message_input.text.strip_edges()
	if text.is_empty() or _is_typing:
		return
	message_input.text = ""
	_hide_welcome()
	_add_user_message(text)
	_send_to_api(text)

func _on_new_chat() -> void:
	_current_chat_id = ""
	for child in message_list.get_children():
		child.queue_free()
	if welcome_screen:
		welcome_screen.show()
		welcome_screen.modulate.a = 1.0
		_update_greeting()
	message_input.grab_focus()

# ─── API Communication ──────────────────────────────────────────────────────
func _send_to_api(text: String) -> void:
	_is_typing = true
	_current_response_label = _add_claude_message_skeleton()
	_start_typing_dots()

	if OS.has_feature("web"):
		_stream_via_web(text)
	else:
		_stream_via_desktop(text)

# ─── Web Export: SSE via JavaScript fetch + ReadableStream ──────────────────
func _stream_via_web(text: String) -> void:
	# Initialize JS queue for bridging SSE events to GDScript
	JavaScriptBridge.eval("window._sq=[];window._sd=false;window._se='';")

	var chat_id_js = "null" if _current_chat_id.is_empty() else _current_chat_id

	# Pass message as JSON-encoded string to avoid injection
	var msg_json = JSON.stringify(text)

	var js := """
	(function(){
		var msgData=%s;msgData.chat_id=%s;
		fetch('%s/api/chat',{
			method:'POST',
			headers:{'Content-Type':'application/json','Authorization':'Bearer %s'},
			body:JSON.stringify(msgData)
		}).then(function(r){
			if(!r.ok)throw new Error('HTTP '+r.status);
			var reader=r.body.getReader();
			var dec=new TextDecoder();
			var buf='';
			function read(){
				reader.read().then(function(res){
					if(res.done){window._sd=true;return;}
					buf+=dec.decode(res.value,{stream:true});
					var lines=buf.split('\\n');
					buf=lines.pop();
					for(var i=0;i<lines.length;i++){
						var l=lines[i].trim();
						if(l.indexOf('data: ')===0){
							try{window._sq.push(l.slice(6));}catch(e){}
						}
					}
					read();
				}).catch(function(e){window._se=e.message;window._sd=true;});
			}
			read();
		}).catch(function(e){window._se=e.message;window._sd=true;});
	})();
	""" % [msg_json, chat_id_js, api_base, auth_token]

	JavaScriptBridge.eval(js)
	_poll_sse_web()

func _poll_sse_web() -> void:
	while true:
		await get_tree().create_timer(0.05).timeout

		# Check for errors
		var err = JavaScriptBridge.eval("window._se")
		if err != null and str(err) != "":
			_stop_typing_dots()
			_append_response("\n[color=#ff6b6b]Error: %s[/color]" % str(err))
			JavaScriptBridge.eval("window._se='';")

		# Drain event queue
		var queue = JavaScriptBridge.eval("window._sq.splice(0)")
		if queue is Array:
			for item in queue:
				if item is String and not item.is_empty():
					var event = JSON.parse_string(item)
					if event is Dictionary:
						_handle_sse_event(event)

		# Check if stream is done
		if JavaScriptBridge.eval("window._sd") == true:
			break

	_stop_typing_dots()
	_is_typing = false
	_scroll_to_bottom()
	_refresh_conversations()

# ─── Desktop: SSE via HTTPClient streaming ──────────────────────────────────
func _stream_via_desktop(text: String) -> void:
	var host_str = api_base.replace("http://", "").replace("https://", "")
	var parts = host_str.split(":")
	var host = parts[0]
	var port = int(parts[1]) if parts.size() > 1 else 3001

	var client = HTTPClient.new()
	var err = client.connect_to_host(host, port)
	if err != OK:
		_stop_typing_dots()
		_append_response("\n[color=#ff6b6b]Connection failed[/color]")
		_is_typing = false
		return

	# Wait for connection
	while client.get_status() == HTTPClient.STATUS_CONNECTING or \
		  client.get_status() == HTTPClient.STATUS_RESOLVING:
		client.poll()
		await get_tree().process_frame

	if client.get_status() != HTTPClient.STATUS_CONNECTED:
		_stop_typing_dots()
		_append_response("\n[color=#ff6b6b]Connection failed[/color]")
		_is_typing = false
		return

	# Build request body
	var body_dict := {"message": text}
	if not _current_chat_id.is_empty():
		body_dict["chat_id"] = int(_current_chat_id)
	var body := JSON.stringify(body_dict).to_utf8_buffer()
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer " + auth_token,
	])

	err = client.request(HTTPClient.METHOD_POST, "/api/chat", headers, body)
	if err != OK:
		_stop_typing_dots()
		_append_response("\n[color=#ff6b6b]Request failed[/color]")
		_is_typing = false
		return

	# Wait for response headers
	while not client.has_response():
		client.poll()
		await get_tree().process_frame

	if client.get_response_code() != 200:
		_stop_typing_dots()
		_append_response("\n[color=#ff6b6b]HTTP %d[/color]" % client.get_response_code())
		_is_typing = false
		return

	# Stream SSE response body
	var buffer := ""
	while client.get_status() != HTTPClient.STATUS_DISCONNECTED:
		client.poll()
		if not client.has_response():
			await get_tree().create_timer(0.01).timeout
			continue
		var chunk = client.read_response_body_chunk()
		if chunk.is_empty():
			await get_tree().create_timer(0.01).timeout
			continue
		buffer += chunk.get_string_from_utf8()

		# Parse SSE lines from buffer
		while true:
			var idx = buffer.find("\n")
			if idx == -1:
				break
			var line = buffer.left(idx).strip_edges()
			buffer = buffer.substr(idx + 1)
			if line.begins_with("data: "):
				var data_str = line.substr(6)
				if data_str == "[DONE]":
					continue
				var event = JSON.parse_string(data_str)
				if event is Dictionary:
					_handle_sse_event(event)

	client.close()
	_stop_typing_dots()
	_is_typing = false
	_scroll_to_bottom()
	_refresh_conversations()

# ─── SSE Event Handler ─────────────────────────────────────────────────────
func _handle_sse_event(event: Dictionary) -> void:
	if not _current_response_label:
		return
	match event.get("type", ""):
		"token":
			_stop_typing_dots()
			_append_response(event.get("content", ""))
		"thinking":
			pass  # Skip thinking tokens for cleaner UI
		"tool_result":
			_append_response("\n[color=#6b6b6b]%s[/color]\n" % event.get("content", ""))
		"tool_calls":
			pass  # Tools executing, wait for results
		"error":
			_stop_typing_dots()
			_append_response("\n[color=#ff6b6b]%s[/color]" % event.get("content", ""))
		"done":
			var chat_id = str(event.get("chat_id", ""))
			if not chat_id.is_empty() and chat_id != "0":
				_current_chat_id = chat_id

func _append_response(text: String) -> void:
	if _current_response_label:
		_current_response_label.append_text(text)
		_scroll_to_bottom()

# ─── Typing Indicator ───────────────────────────────────────────────────────
func _setup_typing_dots() -> void:
	_typing_dots_timer = Timer.new()
	_typing_dots_timer.wait_time = 0.35
	add_child(_typing_dots_timer)
	_typing_dots_timer.timeout.connect(_on_dots_tick)

func _start_typing_dots() -> void:
	_dot_count = 0
	_typing_dots_timer.start()

func _stop_typing_dots() -> void:
	if _typing_dots_timer and not _typing_dots_timer.is_stopped():
		_typing_dots_timer.stop()

func _on_dots_tick() -> void:
	_dot_count = (_dot_count + 1) % 4
	if _current_response_label:
		var dots := "●" * max(_dot_count, 1)
		_current_response_label.text = "[color=#6b6b6b]" + dots + "[/color]"

# ─── Message Rendering ─────────────────────────────────────────────────────
func _add_user_message(text: String) -> void:
	var outer := MarginContainer.new()
	outer.add_theme_constant_override("margin_left", 160)
	outer.add_theme_constant_override("margin_right", 160)
	outer.add_theme_constant_override("margin_top", 12)
	outer.add_theme_constant_override("margin_bottom", 0)

	var align_box := HBoxContainer.new()
	align_box.alignment = BoxContainer.ALIGNMENT_END
	outer.add_child(align_box)

	var bubble := PanelContainer.new()
	var bstyle := StyleBoxFlat.new()
	bstyle.bg_color = C_USER_BUBBLE
	bstyle.set_corner_radius_all(16)
	bstyle.corner_radius_bottom_right = 4
	bstyle.content_margin_left   = 16
	bstyle.content_margin_right  = 16
	bstyle.content_margin_top    = 10
	bstyle.content_margin_bottom = 10
	bubble.add_theme_stylebox_override("panel", bstyle)
	bubble.size_flags_horizontal = Control.SIZE_SHRINK_END
	align_box.add_child(bubble)

	var lbl := RichTextLabel.new()
	lbl.bbcode_enabled         = true
	lbl.fit_content            = true
	lbl.scroll_active          = false
	lbl.add_theme_font_size_override("normal_font_size", 15)
	lbl.add_theme_color_override("default_color", C_TEXT_PRIMARY)
	lbl.text = text
	lbl.custom_minimum_size    = Vector2(100, 0)
	bubble.add_child(lbl)

	message_list.add_child(outer)
	_scroll_to_bottom()

func _add_claude_message_skeleton() -> RichTextLabel:
	var outer := MarginContainer.new()
	outer.add_theme_constant_override("margin_left", 160)
	outer.add_theme_constant_override("margin_right", 160)
	outer.add_theme_constant_override("margin_top", 16)
	outer.add_theme_constant_override("margin_bottom", 0)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	outer.add_child(row)

	# Claude/Sloth icon circle
	var icon_holder := Control.new()
	icon_holder.custom_minimum_size = Vector2(28, 28)
	icon_holder.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(icon_holder)
	_draw_claude_icon_on(icon_holder, 14)

	var content_vbox := VBoxContainer.new()
	content_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content_vbox.add_theme_constant_override("separation", 4)
	row.add_child(content_vbox)

	var name_lbl := Label.new()
	name_lbl.text = "Sloth"
	name_lbl.add_theme_font_size_override("font_size", 13)
	name_lbl.add_theme_color_override("font_color", C_TEXT_MUTED)
	content_vbox.add_child(name_lbl)

	var response_lbl := RichTextLabel.new()
	response_lbl.bbcode_enabled  = true
	response_lbl.fit_content     = true
	response_lbl.scroll_active   = false
	response_lbl.add_theme_font_size_override("normal_font_size", 15)
	response_lbl.add_theme_color_override("default_color", C_TEXT_PRIMARY)
	response_lbl.text            = "[color=#6b6b6b]●[/color]"
	response_lbl.custom_minimum_size = Vector2(200, 0)
	content_vbox.add_child(response_lbl)

	message_list.add_child(outer)
	_scroll_to_bottom()
	return response_lbl

# ─── REST API: Conversations ──────────────────────────────────────────────
func _load_conversations() -> void:
	if OS.has_feature("web"):
		_api_get_web("/api/chats", _on_conversations_loaded)
	else:
		_api_get_desktop("/api/chats", _on_conversations_loaded)

func _on_conversations_loaded(data) -> void:
	for child in conversation_list.get_children():
		child.queue_free()

	if data is Array:
		for conv in data:
			var title = conv.get("title", "Untitled")
			_add_conversation_to_history(title, false)

func _refresh_conversations() -> void:
	_load_conversations()

# ─── REST API: Generic GET ──────────────────────────────────────────────────
func _api_get_web(path: String, callback: Callable) -> void:
	JavaScriptBridge.eval("window._sr='';window._srDone=false;")

	var js := """
		fetch('%s%s',{
			headers:{'Authorization':'Bearer %s'}
		}).then(function(r){return r.json();})
			.then(function(d){window._sr=JSON.stringify(d);window._srDone=true;})
			.catch(function(e){window._sr='[]';window._srDone=true;});
	""" % [api_base, path, auth_token]

	JavaScriptBridge.eval(js)

	while true:
		await get_tree().create_timer(0.1).timeout
		if JavaScriptBridge.eval("window._srDone") == true:
			break

	var result = JavaScriptBridge.eval("window._sr")
	if result is String and not result.is_empty():
		var parsed = JSON.parse_string(result)
		callback.call(parsed)

func _api_get_desktop(path: String, callback: Callable) -> void:
	var http = HTTPRequest.new()
	add_child(http)
	var headers = PackedStringArray(["Authorization: Bearer " + auth_token])
	http.request(api_base + path, headers, HTTPClient.METHOD_GET)
	var result = await http.request_completed
	http.queue_free()

	if result[0] == HTTPRequest.RESULT_SUCCESS:
		var parsed = JSON.parse_string(result[3] as String)
		callback.call(parsed)
	else:
		callback.call(null)

# ─── Welcome screen ────────────────────────────────────────────────────────
func _hide_welcome() -> void:
	if welcome_screen and welcome_screen.visible:
		var tween := create_tween()
		tween.tween_property(welcome_screen, "modulate:a", 0.0, 0.2)
		await tween.finished
		welcome_screen.hide()

func _build_suggestion_cards() -> void:
	for s in SUGGESTIONS:
		var card := _make_suggestion_card(s[0], s[1])
		suggestions_grid.add_child(card)

func _make_suggestion_card(title: String, sub: String) -> PanelContainer:
	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(180, 72)

	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.13, 0.13, 0.13)
	style.border_color = C_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(10)
	style.content_margin_left   = 14
	style.content_margin_right  = 14
	style.content_margin_top    = 12
	style.content_margin_bottom = 12
	card.add_theme_stylebox_override("panel", style)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 4)
	card.add_child(vbox)

	var t := Label.new()
	t.text = title
	t.add_theme_font_size_override("font_size", 13)
	t.add_theme_color_override("font_color", C_TEXT_PRIMARY)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(t)

	var s_lbl := Label.new()
	s_lbl.text = sub
	s_lbl.add_theme_font_size_override("font_size", 12)
	s_lbl.add_theme_color_override("font_color", C_TEXT_MUTED)
	s_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(s_lbl)

	var btn := Button.new()
	btn.flat = true
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.size_flags_vertical   = Control.SIZE_EXPAND_FILL
	btn.pressed.connect(func():
		message_input.text = title + " " + sub
		_on_send_pressed()
	)
	card.add_child(btn)

	return card

# ─── Conversation history sidebar ────────────────────────────────────────────
func _add_conversation_to_history(name: String, prepend: bool = true) -> void:
	var item := _make_conv_item(name)
	if prepend and conversation_list.get_child_count() > 0:
		conversation_list.move_child(item, 0)
	else:
		conversation_list.add_child(item)

func _make_conv_item(name: String) -> Control:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 8)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_top", 0)
	margin.add_theme_constant_override("margin_bottom", 0)

	var btn := Button.new()
	btn.text            = name
	btn.flat            = true
	btn.alignment       = HORIZONTAL_ALIGNMENT_LEFT
	btn.clip_text       = true
	btn.custom_minimum_size = Vector2(0, 34)
	btn.add_theme_font_size_override("font_size", 13)
	btn.add_theme_color_override("font_color",           C_TEXT_SECONDARY)
	btn.add_theme_color_override("font_hover_color",     C_TEXT_PRIMARY)
	btn.add_theme_color_override("font_pressed_color",   C_TEXT_PRIMARY)

	var normal_s := StyleBoxFlat.new()
	normal_s.bg_color = Color(0,0,0,0)
	normal_s.set_corner_radius_all(6)
	normal_s.content_margin_left = 10
	btn.add_theme_stylebox_override("normal", normal_s)

	var hover_s := StyleBoxFlat.new()
	hover_s.bg_color = Color(0.165, 0.165, 0.165)
	hover_s.set_corner_radius_all(6)
	hover_s.content_margin_left = 10
	btn.add_theme_stylebox_override("hover", hover_s)

	margin.add_child(btn)
	return margin

# ─── Scroll helpers ────────────────────────────────────────────────────────
func _scroll_to_bottom() -> void:
	await get_tree().process_frame
	scroll_container.scroll_vertical = int(scroll_container.get_v_scroll_bar().max_value)

# ─── Custom drawing — Claude logo icon ──────────────────────────────────────
func _draw_claude_icon_on(ctrl: Control, radius: float) -> void:
	ctrl.draw.connect(func():
		var center := ctrl.size / 2.0
		var r := radius
		ctrl.draw_arc(center, r, 0, TAU, 32, Color(C_ACCENT, 0.15), 6.0, true)
		for i in range(8):
			var angle := i * TAU / 8.0
			var inner := 0.35 * r
			var outer := r * 0.88
			var p1 := center + Vector2(cos(angle), sin(angle)) * inner
			var p2 := center + Vector2(cos(angle), sin(angle)) * outer
			var alpha := 1.0 if i % 2 == 0 else 0.55
			ctrl.draw_line(p1, p2, Color(C_ACCENT, alpha), 1.8, true)
		ctrl.draw_circle(center, 2.5, C_ACCENT)
	)
	ctrl.queue_redraw()

# ─── Helpers ────────────────────────────────────────────────────────────────
func _escape_js(text: String) -> String:
	return (text
		.replace("\\", "\\\\")
		.replace("'", "\\'")
		.replace("\n", "\\n")
		.replace("\r", "")
		.replace("\t", "\\t"))
