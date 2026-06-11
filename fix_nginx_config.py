#!/usr/bin/env python3
"""
Temporarily fix nginx config to allow certbot to run
Removes SSL block for cencan.mininglifeserver.com and allows HTTP
"""

config_path = "/etc/nginx/sites-enabled/mininglifeserver.com"
output_path = "/tmp/mininglifeserver.com.fixed"

with open(config_path, 'r') as f:
    lines = f.readlines()

output_lines = []
skip_block = False
in_cencan_ssl = False
brace_count = 0

for i, line in enumerate(lines):
    # Check if we're entering the cencan SSL block
    if 'server {' in line:
        # Look ahead to see if this is the cencan SSL block
        next_lines = lines[i:min(i+10, len(lines))]
        is_cencan_ssl = any(
            'cencan.mininglifeserver.com' in l and 'listen 443 ssl' in ''.join(next_lines[:5])
            for l in next_lines
        )
        if is_cencan_ssl:
            in_cencan_ssl = True
            skip_block = True
            brace_count = 1
            output_lines.append("# Temporarily disabled for certbot - SSL block for cencan.mininglifeserver.com\n")
            output_lines.append("# " + line)
            continue
    
    # If we're in the block to skip, comment out lines and track braces
    if skip_block:
        if '{' in line:
            brace_count += line.count('{')
        if '}' in line:
            brace_count -= line.count('}')
        
        output_lines.append("# " + line)
        
        if brace_count == 0:
            skip_block = False
            in_cencan_ssl = False
            output_lines.append("\n")
        continue
    
    # Remove redirect for cencan HTTP block
    if 'cencan.mininglifeserver.com' in line and i < len(lines) - 5:
        # Check if next few lines have redirect
        next_lines = lines[i:i+5]
        has_redirect = any('return 301 https://' in l for l in next_lines)
        if has_redirect:
            output_lines.append(line)
            # Skip until we find the closing brace of this block
            j = i + 1
            while j < len(lines):
                if 'return 301 https://' in lines[j]:
                    output_lines.append("    # Temporarily disabled redirect for certbot\n")
                    output_lines.append("    # " + lines[j])
                    # Add a simple proxy pass instead
                    output_lines.append("    location / {\n")
                    output_lines.append("        proxy_pass http://127.0.0.1:9001;\n")
                    output_lines.append("        proxy_set_header Host $host;\n")
                    output_lines.append("        proxy_set_header X-Real-IP $remote_addr;\n")
                    output_lines.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n")
                    output_lines.append("        proxy_set_header X-Forwarded-Proto $scheme;\n")
                    output_lines.append("    }\n")
                    j += 1
                elif lines[j].strip() == '}':
                    output_lines.append(lines[j])
                    break
                else:
                    j += 1
            # Skip past what we just processed
            while i < j:
                i += 1
                if i < len(lines):
                    continue
            continue
    
    output_lines.append(line)

with open(output_path, 'w') as f:
    f.writelines(output_lines)

print(f"Fixed config written to {output_path}")
print("Review it and then copy it to the actual location")

