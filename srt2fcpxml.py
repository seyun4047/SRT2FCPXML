import re
import uuid
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

def parse_srt_time(time_str):
    """SRT -> timecode"""
    hours, minutes, seconds = time_str.split(':')
    seconds, milliseconds = seconds.split(',')
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000
    return total_seconds

def seconds_to_frames(seconds, framerate=60):
    """sec -> frame"""
    return int(seconds * framerate)

def frames_to_fcpxml_time(frames, framerate=60):
    """frame to FCPXML timecode"""
    return f"{frames}/{framerate}s"

def parse_srt(srt_content):
    """parsing SRT"""
    subtitles = []
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.*\n?)+?)(?=\n\d+\n|\Z)'

    matches = re.finditer(pattern, srt_content, re.MULTILINE)

    for match in matches:
        index = int(match.group(1))
        start_time = parse_srt_time(match.group(2))
        end_time = parse_srt_time(match.group(3))
        text = match.group(4).strip()

        subtitles.append({
            'index': index,
            'start': start_time,
            'end': end_time,
            'duration': end_time - start_time,
            'text': text
        })

    return subtitles

def generate_uid():
    """Create UUID"""
    return uuid.uuid4().hex.upper()

def create_fcpxml(subtitles, project_name="Subtitles", framerate=60):
    """Create FCPXML"""
    # FCPXML 루트 생성
    fcpxml = ET.Element('fcpxml', version="1.9")

    # resource section
    resources = ET.SubElement(fcpxml, 'resources')

    # format ex) fhd 60p
    format_elem = ET.SubElement(resources, 'format', {
        'id': 'r1',
        'name': f'FFVideoFormat1080p{framerate}',
        'frameDuration': f'1/{framerate}s',
        'width': '1920',
        'height': '1080',
        'colorSpace': '1-1-1 (Rec. 709)'
    })

    # Basic Title effect resource
    effect = ET.SubElement(resources, 'effect', {
        'id': 'r2',
        'name': 'Basic Title',
        'uid': '.../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti'
    })

    # Create library
    library = ET.SubElement(fcpxml, 'library')

    # Create event
    event_uid = generate_uid()
    event = ET.SubElement(library, 'event', {
        'name': project_name,
        'uid': event_uid
    })

    # Create project
    project_uid = generate_uid()
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S +0000")
    project = ET.SubElement(event, 'project', {
        'name': project_name,
        'uid': project_uid,
        'modDate': current_time
    })

    # Calculate length
    total_duration_frames = seconds_to_frames(subtitles[-1]['end'], framerate) if subtitles else 0

    # Create sequence
    sequence = ET.SubElement(project, 'sequence', {
        'format': 'r1',
        'duration': frames_to_fcpxml_time(total_duration_frames, framerate),
        'tcStart': f'0/{framerate}s',
        'tcFormat': 'NDF',
        'audioLayout': 'stereo',
        'audioRate': '48k'
    })

    spine = ET.SubElement(sequence, 'spine')

    # Gap(background)
    gap = ET.SubElement(spine, 'gap', {
        'name': 'Gap',
        'offset': '0s',
        'start': '0s',
        'duration': frames_to_fcpxml_time(total_duration_frames, framerate)
    })

    # Each sub → title
    for i, sub in enumerate(subtitles):
        start_frames = seconds_to_frames(sub['start'], framerate)
        duration_frames = seconds_to_frames(sub['duration'], framerate)

        title = ET.SubElement(gap, 'title', {
            'ref': 'r2',
            'lane': '1',
            'name': f'{sub["text"][:30]} - Basic Title',
            'offset': frames_to_fcpxml_time(start_frames, framerate),
            'start': f'0/{framerate}s',
            'duration': frames_to_fcpxml_time(duration_frames, framerate)
        })

        # Flatten parameter
        ET.SubElement(title, 'param', {
            'name': 'Flatten',
            'key': '9999/999166631/999166633/2/351',
            'value': '1'
        })

        # Alignment 1
        ET.SubElement(title, 'param', {
            'name': 'Alignment',
            'key': '9999/999166631/999166633/2/354/3142713059/401',
            'value': '1 (Center)'
        })

        # Alignment 2
        ET.SubElement(title, 'param', {
            'name': 'Alignment',
            'key': '9999/999166631/999166633/2/354/999169573/401',
            'value': '1 (Center)'
        })

        # Text
        text_elem = ET.SubElement(title, 'text')
        text_style = ET.SubElement(text_elem, 'text-style', {
            'ref': f'ts{i + 1}'
        })
        text_style.text = sub['text']

        # Define Text style
        text_style_def = ET.SubElement(title, 'text-style-def', {
            'id': f'ts{i + 1}'
        })
        ET.SubElement(text_style_def, 'text-style', {
            'font': 'Helvetica',
            'fontSize': '60',
            'fontColor': '1 1 1 1',
            'alignment': 'center',
            'fontFace': 'Regular'
        })

    # Add smart collection
    smart_collections = [
        ('Projects', 'all', [('clip', 'is', 'project')]),
        ('All Video', 'any', [('media', 'is', 'videoOnly'), ('media', 'is', 'videoWithAudio')]),
        ('Audio Only', 'all', [('media', 'is', 'audioOnly')]),
        ('Stills', 'all', [('media', 'is', 'stills')]),
    ]

    for name, match_type, rules in smart_collections:
        smart_coll = ET.SubElement(library, 'smart-collection', {
            'name': name,
            'match': match_type
        })
        for rule_type, rule_attr, rule_value in rules:
            ET.SubElement(smart_coll, f'match-{rule_type}', {
                'rule': rule_attr,
                'type': rule_value
            })

    # Favorites smart collection
    favorites = ET.SubElement(library, 'smart-collection', {
        'name': 'Favorites',
        'match': 'all'
    })
    ET.SubElement(favorites, 'match-ratings', {'value': 'favorites'})

    return fcpxml

def prettify_xml(elem):
    """formatting XML"""
    rough_string = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
    lines = pretty.split('\n')[1:]
    lines = [line for line in lines if line.strip()]
    return '\n'.join(lines)

def srt_to_fcpxml(srt_file_path, fcpxml_file_path, project_name=None, framerate=60):
    """SRT -> FCPXML"""
    # Read SRT
    with open(srt_file_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    # default project name
    if project_name is None:
        import os
        project_name = os.path.splitext(os.path.basename(srt_file_path))[0]

    # parsing SRT
    subtitles = parse_srt(srt_content)
    print(f"Find {len(subtitles)} subtitles!'")

    if not subtitles:
        print("Cannot find the subtitles. Please check your SRT file.")
        return

    # Create FCPXML
    fcpxml = create_fcpxml(subtitles, project_name, framerate)

    # Save FCPXML
    xml_string = prettify_xml(fcpxml)
    with open(fcpxml_file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE fcpxml>\n')
        f.write(xml_string)

    print(f"Success! FCPXML: {fcpxml_file_path}")

# ex
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("How?: python3 srt2fcpxml.py <input.srt> <output.fcpxml> [framerate] [project_name]")
        print("ex: python3 srt2fcpxml.py 251006.srt output.fcpxml 60 \"My Subtitles\"")
        sys.exit(1)

    input_srt = sys.argv[1]
    output_fcpxml = sys.argv[2]
    framerate = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    project_name = sys.argv[4] if len(sys.argv) > 4 else None

    # play
    srt_to_fcpxml(input_srt, output_fcpxml, project_name, framerate)