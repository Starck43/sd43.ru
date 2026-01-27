from os import path

from django.contrib.admin.widgets import AdminFileWidget
from django.utils.safestring import mark_safe

from exhibition.logic import is_image_file, get_image_url, is_file_exist


class MediaWidget(AdminFileWidget):
	def render(self, name, value, attrs=None, renderer=None):
		is_image = is_image_file(value)
		is_video = False  # is_video_file(value)
		background_color = "white" if name == 'image' else "transparent"

		output = []

		if value and getattr(value, "url", None):
			file_url = get_image_url(value) or value.url

			if is_image:
				# Для SVG используем inline отображение с сохранением ваших стилей
				tag = (
					f'<img class="upload-image immage-{name} mb-3" '
					f'src="{file_url}" '
					f'alt="{value}" '
					f'style="width: 100%; height: auto; max-width: 200px; background: {background_color}; '
					f'border: 1px solid #ccc; border-radius: 3px;"/>'
				)
			elif is_video:
				tag = f'<video src="{file_url}" controls style="width: 100%; height: auto; max-width: 200px;"/>'
			else:
				tag = value

			output.append(
				f'<a href="{file_url}" target="_blank" style="display: flex; flex-wrap: wrap; gap: 5px; width: 100%;">{tag}</a>'
			)

			if not self.is_required:
				output.append(f'''
					<div class="clearable-file-input mb-3">
						<input type="checkbox" name="{name}-clear" id="{name}-clear_id">
						<label for="{name}-clear_id" class="form-check-label">Очистить</label>
					</div>
				''')

		# Остальной код остается без изменений
		output.append(f'''
			<div class="button-group group-{name}" style="width: 100%; max-width: 300px;">
				<button type="button" class="btn btn-success btn-sm" data-id="{attrs["id"]}">
					{"Загрузить файл" if not value or not getattr(value, "url", None) else "Изменить файл"}
				</button>
				<div class="file-upload" style="display: none;">
					<input type="file" name="{name}" {"accept=image/*" if self.attrs else "accept=video/*"} id="{attrs["id"]}"/>
				</div>
			</div>
		''')

		output.append(f'''
			<script>
				document.querySelector("button[data-id={attrs["id"]}]")?.addEventListener("click", () =>
				document.querySelector("#{attrs["id"]}")?.click())
			</script>
		''')

		# Скрипт для предпросмотра SVG
		if name in ['logo', 'image']:  # поля, где могут быть SVG
			output.append(f'''
				<script>
					document.querySelector('#{attrs["id"]}').addEventListener('change', function() {{
						var file = this.files[0];
						if (file) {{
							if (file.type === 'image/svg+xml' || file.name.toLowerCase().endsWith('.svg')) {{
								var reader = new FileReader();
								reader.onload = function(e) {{
									var container = document.querySelector('.upload-svg-container.immage-{name}');
									var previewDiv = document.createElement('div');
									previewDiv.className = 'upload-svg-container immage-{name} mb-3';
									previewDiv.style = 'width: 100%; max-width: 200px; background: {background_color}; border: 1px solid #ccc; border-radius: 3px; padding: 5px;';
									previewDiv.innerHTML = e.target.result;
									
									// Заменяем старый превью или добавляем новый
									var buttonGroup = document.querySelector('.group-{name}');
									var existingPreview = document.querySelector('.immage-{name}');
									if (existingPreview) {{
										existingPreview.parentNode.replaceChild(previewDiv, existingPreview);
									}} else {{
										buttonGroup.parentNode.insertBefore(previewDiv, buttonGroup);
									}}
								}};
								reader.readAsText(file);
							}} else {{
								var reader = new FileReader();
								reader.onload = function(e) {{
									var img = document.querySelector('.immage-{name}');
									if (img) {{
										img.src = e.target.result;
									}} else {{
										img = document.createElement('img');
										img.className = 'upload-image immage-{name} mb-3';
										img.alt = file.name;
										img.src = e.target.result;
										img.style = 'width:100%;height:auto;max-width:200px; background:{background_color}; border:1px solid #ccc; border-radius:3px;';
										var buttonGroup = document.querySelector('.group-{name}');
										buttonGroup.parentNode.insertBefore(img, buttonGroup);
									}}
								}};
								reader.readAsDataURL(file);
							}}
						}}
					}});
				</script>
			''')

		return mark_safe(''.join(output))
