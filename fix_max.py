with open("pdf_builder.py", "r") as f:
    content = f.read()

content = content.replace("mx = max(*data, 1)", "mx = max(max(data), 1)")

with open("pdf_builder.py", "w") as f:
    f.write(content)

