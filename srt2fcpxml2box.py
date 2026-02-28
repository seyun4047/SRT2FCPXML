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

# ----------MY-CUSTOM-TITLE---------------------------------------------------------------
def create_fcpxml(subtitles, project_name="Subtitles", framerate=60):
    """Create FCPXML"""
    fcpxml = ET.Element('fcpxml', version="1.13")

    # resource section
    resources = ET.SubElement(fcpxml, 'resources')

    # 4K 60fps
    format_elem = ET.SubElement(resources, 'format', {
        'id': 'r1',
        'name': f'FFVideoFormat3840x2160p{framerate}',
        'frameDuration': '100/6000s',  # 원본 XML에 맞춤
        'width': '3840',
        'height': '2160',
        'colorSpace': '1-1-1 (Rec. 709)'
    })

    # custom motion title
    ET.SubElement(resources, 'effect', {
        'id': 'r2',
        'name': '멋진프레임 텍스트',
        'uid': '~/Titles.localized/멋진프레임/멋진프레임 텍스트/멋진프레임 텍스트.moti',
        'src': 'file:///your_moti_custom_file_url.moti'
    })

    # library
    library = ET.SubElement(fcpxml, 'library', {
        'location': 'file:///your_title_custom_file_url/mutzin_title.fcpbundle/'
    })

    event_uid = generate_uid()
    event = ET.SubElement(library, 'event', {
        'name': datetime.now().strftime("%Y. %m. %d."),
        'uid': event_uid
    })

    project_uid = generate_uid()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S +0900")
    project = ET.SubElement(event, 'project', {
        'name': "title_project",
        'uid': project_uid,
        'modDate': current_time
    })

    total_duration_frames = seconds_to_frames(subtitles[-1]['end'], framerate) if subtitles else 0
    sequence = ET.SubElement(project, 'sequence', {
        'format': 'r1',
        'duration': frames_to_fcpxml_time(total_duration_frames, framerate),
        'tcStart': '0s',
        'tcFormat': 'NDF',
        'audioLayout': 'stereo',
        'audioRate': '48k'
    })

    spine = ET.SubElement(sequence, 'spine')

    # Each sub → title
    for i, sub in enumerate(subtitles):
        start_frames = seconds_to_frames(sub['start'], framerate)
        duration_frames = seconds_to_frames(sub['duration'], framerate)

        title = ET.SubElement(spine, 'title', {
            'ref': 'r2',
            'offset': frames_to_fcpxml_time(start_frames, framerate),
            'name': '멋진프레임 텍스트',
            'start': '3600s',
            'duration': frames_to_fcpxml_time(duration_frames, framerate)
        })

        text_elem = ET.SubElement(title, 'text')
        text_style = ET.SubElement(text_elem, 'text-style', {'ref': f'ts{i+1}'})
        text_style.text = sub['text']

        style_def = ET.SubElement(title, 'text-style-def', {'id': f'ts{i+1}'})
        ET.SubElement(style_def, 'text-style', {
            'font': 'S-Core Dream',
            'fontSize': '79',
            'fontFace': '3 Light',
            'fontColor': '1 1 1 1',
            'alignment': 'center'
        })

    # smart collections
    smart_collections = [
        ('프로젝트', 'all', [('clip', 'is', 'project')]),
        ('모든 비디오', 'any', [('media', 'is', 'videoOnly'), ('media', 'is', 'videoWithAudio')]),
        ('오디오만', 'all', [('media', 'is', 'audioOnly')]),
        ('스틸 사진', 'all', [('media', 'is', 'stills')]),
    ]

    for name, match_type, rules in smart_collections:
        smart_coll = ET.SubElement(library, 'smart-collection', {'name': name, 'match': match_type})
        for rule_type, rule_attr, rule_value in rules:
            ET.SubElement(smart_coll, f'match-{rule_type}', {'rule': rule_attr, 'type': rule_value})

    favorites = ET.SubElement(library, 'smart-collection', {'name': '선호하는 구간', 'match': 'all'})
    ET.SubElement(favorites, 'match-ratings', {'value': 'favorites'})

    return fcpxml
# ----------MY-CUSTOM-TITLE---------------------------------------------------------------

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
        print("How?: python3 srt2fcpxml2box.py <input.srt> <output.fcpxml> [framerate] [project_name]")
        print("ex: python3 srt2fcpxml2box.py 251006.srt output.fcpxml 60 \"My Subtitles\"")
        sys.exit(1)

    input_srt = sys.argv[1]
    output_fcpxml = sys.argv[2]
    framerate = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    project_name = sys.argv[4] if len(sys.argv) > 4 else None

    # play
    srt_to_fcpxml(input_srt, output_fcpxml, project_name, framerate)