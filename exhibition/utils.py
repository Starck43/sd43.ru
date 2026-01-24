def is_exhibitor_of_exhibition(user, exhibition):
	"""Проверка, является ли пользователь участником выставки"""
	if not user or not user.is_authenticated:
		return False
	
	return exhibition.exhibitors.filter(user=user).exists()	
