from werkzeug.security import generate_password_hash

# The plaintext password we will use
PLAINTEXT_PASSWORD = 'finalpassword123' 

# Generate the modern, compatible hash
hashed_password = generate_password_hash(PLAINTEXT_PASSWORD, method='pbkdf2:sha256', salt_length=16)

print("-" * 50)
print(f"PLAINTEXT: {PLAINTEXT_PASSWORD}")
print(f"NEW HASH: {hashed_password}")
print("-" * 50)