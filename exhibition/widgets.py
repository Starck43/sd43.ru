from django.contrib.admin.widgets import AdminFileWidget
from django.utils.safestring import mark_safe

from exhibition.logic import get_image_url


class MediaWidget(AdminFileWidget):
	def __init__(self, attrs=None, field=None):
		super().__init__(attrs)
		self.field = field  # Сохраняем переданное поле

	def render(self, name, value, attrs=None, renderer=None):
		# Базовые атрибуты
		default_accept = 'image/*'

		if hasattr(self, 'field') and hasattr(self.field, 'accept'):
			accept_value = self.field.accept
			if accept_value:
				if isinstance(accept_value, (list, tuple)):
					default_accept = ','.join(accept_value)
				elif isinstance(accept_value, str):
					default_accept = accept_value

		# Получаем attrs с id
		if attrs is None:
			attrs = {}
		widget_id = attrs.get('id', f"id_{name}")

		output = []
		preview_id = f"preview-{widget_id}"
		default_attrs = f'accept="{default_accept}"'
		background_color = "transparent"

		# Определяем accept атрибут в зависимости от типа текущего файла
		if value and getattr(value, "url", None):

			file_url = get_image_url(value) or value.url

			# Создаем тег для отображения превью
			tag = f'<img class="upload-image immage-{name} mb-3" '
			tag += f'src="{file_url}" '
			tag += f'alt="{value}" '
			tag += f'id="{preview_id}" '
			tag += f'style="width: 100%; height: auto; max-width: 200px; background: {background_color}; '
			tag += 'border: 1px solid #ccc; border-radius: 3px;"/>'

			output.append(
				f'<a href="{file_url}" target="_blank" style="display: flex; flex-wrap: wrap; gap: 5px; width: 100%;">{tag}</a>'
			)

			if not self.is_required:
				checkbox_html = f'''
				<div class="clearable-file-input mb-3">
					<input type="checkbox" name="{name}-clear" id="{name}-clear_id">
					<label for="{name}-clear_id" class="form-check-label">Очистить</label>
				</div>
				'''
				output.append(checkbox_html)

		# Кнопка и input
		button_text = "Загрузить файл" if not value or not getattr(value, "url", None) else "Изменить файл"
		button_html = f'''
		<div class="button-group group-{name}" style="width: 100%; max-width: 300px;">
			<button type="button" class="btn btn-success btn-sm" data-id="{widget_id}">
				{button_text}
			</button>
			<div class="file-upload" style="display: none;">
				<input type="file" name="{name}" {default_attrs} id="{widget_id}"/>
			</div>
		</div>
		'''
		output.append(button_html)

		# Скрипт для открытия диалога выбора файла
		script_html = f'''
		<script>
			document.querySelector("button[data-id='{widget_id}']").addEventListener("click", function() {{
				document.getElementById("{widget_id}").click();
			}});
		</script>
		'''
		output.append(script_html)

		# Скрипт для предпросмотра
		preview_script = f'''
		<script>
			document.getElementById("{widget_id}").addEventListener("change", function(event) {{
				var file = this.files[0];
				if (!file) return;

				var isSvg = file.type === "image/svg+xml" || file.name.toLowerCase().endsWith(".svg");
				var reader = new FileReader();

				reader.onload = function(e) {{
					var existingPreview = document.getElementById("{preview_id}");

					if (existingPreview) {{
						// Обновляем существующее превью
						existingPreview.src = e.target.result;
						// Обновляем ссылку
						var link = existingPreview.closest("a");
						if (link) {{
							link.href = e.target.result;
						}}
					}} else {{
						// Создаем новое превью
						var img = document.createElement("img");
						img.className = "upload-image immage-{name} mb-3";
						img.id = "{preview_id}";
						img.src = e.target.result;
						img.alt = file.name;
						img.style.cssText = "width: 100%; height: auto; max-width: 200px; background: {background_color}; border: 1px solid #ccc; border-radius: 3px;";

						var link = document.createElement("a");
						link.href = e.target.result;
						link.target = "_blank";
						link.style.cssText = "display: flex; flex-wrap: wrap; gap: 5px; width: 100%;";
						link.appendChild(img);

						var buttonGroup = document.querySelector(".group-{name}");
						if (buttonGroup) {{
							buttonGroup.parentNode.insertBefore(link, buttonGroup);
							buttonGroup.querySelector("button").textContent = "Изменить файл";
						}}

						// Добавляем чекбокс "очистить" если поле не обязательно
						{'if (!document.getElementById("{name}-clear_id")) {' if not self.is_required else ''}
						{'var clearDiv = document.createElement("div");' if not self.is_required else ''}
						{'clearDiv.className = "clearable-file-input mb-3";' if not self.is_required else ''}
						{'clearDiv.innerHTML = \'<input type="checkbox" name="{name}-clear" id="{name}-clear_id"><label for="{name}-clear_id" class="form-check-label">Очистить</label>\';' if not self.is_required else ''}
						{'link.parentNode.insertBefore(clearDiv, link.nextSibling);' if not self.is_required else ''}
						{'}' if not self.is_required else ''}
					}}
				}};

				// Читаем файл в зависимости от типа
				reader.readAsDataURL(file);
			}});
		</script>
		'''
		output.append(preview_script)

		return mark_safe(''.join(output))
