import bcrypt

print('version', bcrypt.__version__)
print('has_about', hasattr(bcrypt, '__about__'))
print('attrs containing about:', [a for a in dir(bcrypt) if 'about' in a.lower()])
