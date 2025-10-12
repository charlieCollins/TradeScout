#!/usr/bin/env python3
"""Migrate gap candidates from text report files to database."""

import sys
import re
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.database_manager import DatabaseManager
from database.managers import AssetManager


def parse_report_header(lines):
    """Parse report header to extract metadata."""
    metadata = {}

    for line in lines:
        if line.startswith("Generated:"):
            # Extract timestamp: "Generated: 2025-10-09 08:44:09"
            match = re.search(r"Generated: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if match:
                metadata['analysis_timestamp'] = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

        elif line.startswith("Session:"):
            # Extract session: "Session: premarket"
            match = re.search(r"Session: (\w+)", line)
            if match:
                metadata['session_type'] = match.group(1)

        elif line.startswith("Date:"):
            # Extract date: "Date: 2025-10-09"
            match = re.search(r"Date: (\d{4}-\d{2}-\d{2})", line)
            if match:
                metadata['trading_date'] = date.fromisoformat(match.group(1))

    return metadata


def parse_viable_candidate(section_text, metadata):
    """Parse a viable candidate section."""
    candidate = metadata.copy()

    lines = section_text.split('\n')

    # First line has number and symbol/name: "1. ASST - Strive, Inc. Class A Common Stock"
    first_line = lines[0]
    match = re.search(r'^\d+\.\s+([A-Z]+)\s+-\s+(.+)$', first_line)
    if match:
        candidate['symbol'] = match.group(1)
        candidate['name'] = match.group(2).strip()

    for line in lines:
        # Current Price: $1.05
        if "Current Price:" in line:
            match = re.search(r'\$([0-9,.]+)', line)
            if match:
                candidate['current_price'] = float(match.group(1).replace(',', ''))

        # Reference Price: $1.55
        elif "Reference Price:" in line:
            match = re.search(r'\$([0-9,.]+)', line)
            if match:
                candidate['reference_price'] = float(match.group(1).replace(',', ''))

        # Gap: -32.48% (down)
        elif "Gap:" in line and "%" in line:
            match = re.search(r'([+-]?\d+\.\d+)%\s+\((\w+)\)', line)
            if match:
                candidate['gap_percentage'] = float(match.group(1))
                candidate['gap_direction'] = match.group(2)

        # Market Cap: $1.69B
        elif "Market Cap:" in line:
            match = re.search(r'\$([0-9,.]+)([BMK])', line)
            if match:
                value = float(match.group(1).replace(',', ''))
                multiplier = match.group(2)
                if multiplier == 'B':
                    candidate['market_cap'] = value * 1e9
                elif multiplier == 'M':
                    candidate['market_cap'] = value * 1e6
                elif multiplier == 'K':
                    candidate['market_cap'] = value * 1e3

        # Extended Hours Volume: 27,026,870.0 shares
        elif "Extended Hours Volume:" in line:
            match = re.search(r'([0-9,]+\.?\d*)\s+shares', line)
            if match:
                candidate['extended_hours_volume'] = int(float(match.group(1).replace(',', '')))

        # Previous Day Volume: 18,850,774 shares
        elif "Previous Day Volume:" in line:
            match = re.search(r'([0-9,]+)\s+shares', line)
            if match:
                candidate['previous_day_volume'] = int(match.group(1).replace(',', ''))

        # Volume Ratio: 2.33x
        elif "Volume Ratio:" in line and "x" in line:
            match = re.search(r'([0-9.]+)x', line)
            if match:
                candidate['volume_ratio'] = float(match.group(1))

        # Catalyst Score: 0/100
        elif "Catalyst Score:" in line:
            match = re.search(r'(\d+)/100', line)
            if match:
                candidate['catalyst_score'] = int(match.group(1))

        # Quality Score: 56/100
        elif "Quality Score:" in line:
            match = re.search(r'(\d+)/100', line)
            if match:
                candidate['quality_score'] = int(match.group(1))

        # Risk Level: HIGH
        elif "Risk Level:" in line:
            match = re.search(r'Risk Level:\s+(\w+)', line)
            if match:
                candidate['risk_level'] = match.group(1).lower()

    # Determine quality tier from quality score
    if 'quality_score' in candidate:
        score = candidate['quality_score']
        if score >= 85:
            candidate['quality_tier'] = 'excellent'
        elif score >= 70:
            candidate['quality_tier'] = 'good'
        elif score >= 60:
            candidate['quality_tier'] = 'fair'
        else:
            candidate['quality_tier'] = 'poor'

    # Set filter flags for passed candidates
    candidate['passed_gap_filter'] = True
    candidate['passed_market_cap_filter'] = True
    candidate['passed_volume_filter'] = True
    candidate['passed_exhaustion_filter'] = True

    # Check if it's a Friday gap
    candidate['is_friday_gap'] = candidate['trading_date'].weekday() == 4

    # Set status
    if candidate['is_friday_gap']:
        candidate['status'] = 'warning'
        candidate['rejection_reason'] = 'Friday gap - weekend risk'
    else:
        candidate['status'] = 'passed'
        candidate['rejection_reason'] = None

    return candidate


def parse_failed_candidate(line_text, metadata):
    """Parse a failed candidate from the top candidates list."""
    candidate = metadata.copy()

    # Example: "1. DGNX (Diginex Limited Ordinary Shares)"
    match = re.search(r'^\d+\.\s+([A-Z]+)\s+\((.+)\)', line_text)
    if not match:
        return None

    candidate['symbol'] = match.group(1)
    candidate['name'] = match.group(2).strip()

    # Parse second line: "   Gap: +28.36%  |  Price: $39.78  |  MCap: $3.2B"
    # Parse third line: "   Volume Ratio: 0.17x  |  Extended Hours Vol: 272,381"

    return candidate


def parse_multiline_failed_candidate(lines, metadata):
    """Parse a multi-line failed candidate entry."""
    if len(lines) < 2:
        return None

    candidate = metadata.copy()

    # First line: "1. DGNX (Diginex Limited Ordinary Shares)"
    match = re.search(r'^\d+\.\s+([A-Z]+)\s+\((.+)\)', lines[0])
    if not match:
        return None

    candidate['symbol'] = match.group(1)
    candidate['name'] = match.group(2).strip()

    # Second line: "   Gap: +28.36%  |  Price: $39.78  |  MCap: $3.2B"
    gap_line = lines[1]

    # Extract gap
    match = re.search(r'Gap:\s+([+-]?\d+\.\d+)%', gap_line)
    if match:
        candidate['gap_percentage'] = float(match.group(1))
        candidate['gap_direction'] = 'up' if candidate['gap_percentage'] > 0 else 'down'

    # Extract price
    match = re.search(r'Price:\s+\$([0-9,.]+)', gap_line)
    if match:
        candidate['current_price'] = float(match.group(1).replace(',', ''))

    # Calculate reference price from gap % and current price if we have both
    if 'gap_percentage' in candidate and 'current_price' in candidate:
        # gap_percentage = ((current - reference) / reference) * 100
        # reference = current / (1 + gap_percentage/100)
        gap_pct = candidate['gap_percentage']
        current = candidate['current_price']
        candidate['reference_price'] = current / (1 + gap_pct / 100)

    # Extract market cap
    match = re.search(r'MCap:\s+\$([0-9,.]+)([BMK])', gap_line)
    if match:
        value = float(match.group(1).replace(',', ''))
        multiplier = match.group(2)
        if multiplier == 'B':
            candidate['market_cap'] = value * 1e9
        elif multiplier == 'M':
            candidate['market_cap'] = value * 1e6

    # Third line: "   Volume Ratio: 0.17x  |  Extended Hours Vol: 272,381"
    if len(lines) >= 3:
        vol_line = lines[2]

        # Extract volume ratio
        match = re.search(r'Volume Ratio:\s+([0-9.]+)x', vol_line)
        if match:
            candidate['volume_ratio'] = float(match.group(1))
        elif "N/A" in vol_line:
            candidate['volume_ratio'] = None

        # Extract extended hours volume
        match = re.search(r'Extended Hours Vol:\s+([0-9,]+)', vol_line)
        if match:
            candidate['extended_hours_volume'] = int(match.group(1).replace(',', ''))

    # Set filter flags for failed candidates
    candidate['passed_gap_filter'] = True
    candidate['passed_market_cap_filter'] = True
    candidate['passed_volume_filter'] = False  # Failed volume
    candidate['passed_exhaustion_filter'] = True
    candidate['status'] = 'rejected'
    candidate['rejection_reason'] = 'Volume ratio < 1.5x'
    candidate['is_friday_gap'] = candidate['trading_date'].weekday() == 4

    return candidate


def insert_gap_result(cursor, candidate, asset_id):
    """Insert a gap result into the database."""

    # Use reference_price as prevday_close (close approximation for premarket/afterhours)
    prevday_close = candidate.get('reference_price', 0.0)

    cursor.execute("""
        INSERT INTO gap_results (
            asset_id, analysis_timestamp, session_type, trading_date,
            gap_percentage, gap_direction,
            reference_price, current_price, prevday_close,
            extended_hours_volume, previous_day_volume, volume_ratio,
            market_cap,
            quality_score, quality_tier, catalyst_score,
            passed_gap_filter, passed_volume_filter, passed_market_cap_filter,
            passed_exhaustion_filter, is_friday_gap,
            status, rejection_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        asset_id,
        candidate.get('analysis_timestamp'),
        candidate.get('session_type'),
        candidate.get('trading_date'),
        candidate.get('gap_percentage'),
        candidate.get('gap_direction'),
        candidate.get('reference_price'),
        candidate.get('current_price'),
        prevday_close,
        candidate.get('extended_hours_volume'),
        candidate.get('previous_day_volume'),
        candidate.get('volume_ratio'),
        candidate.get('market_cap'),
        candidate.get('quality_score'),
        candidate.get('quality_tier'),
        candidate.get('catalyst_score'),
        candidate.get('passed_gap_filter', True),
        candidate.get('passed_volume_filter', False),
        candidate.get('passed_market_cap_filter', True),
        candidate.get('passed_exhaustion_filter', True),
        candidate.get('is_friday_gap', False),
        candidate.get('status', 'rejected'),
        candidate.get('rejection_reason')
    ))
    return cursor.lastrowid


def process_report_file(filepath, db_manager, asset_manager):
    """Process a single report file."""
    print(f"\nProcessing: {filepath.name}")

    with open(filepath, 'r') as f:
        content = f.read()

    lines = content.split('\n')

    # Parse header
    metadata = parse_report_header(lines[:20])
    print(f"  Date: {metadata.get('trading_date')}")
    print(f"  Session: {metadata.get('session_type')}")
    print(f"  Analysis: {metadata.get('analysis_timestamp')}")

    saved_count = 0

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Find and parse VIABLE CANDIDATES section
        viable_start = None
        for i, line in enumerate(lines):
            if "VIABLE CANDIDATES" in line:
                viable_start = i
                break

        if viable_start:
            # Parse viable candidates (detailed format)
            # Find all candidate sections (start with number + period)
            candidate_sections = []
            current_section = []

            for i in range(viable_start + 3, len(lines)):
                line = lines[i]

                # Check if we've reached the end of viable candidates
                if line.startswith("==="):
                    if current_section:
                        candidate_sections.append('\n'.join(current_section))
                    break

                # Check if this is the start of a new candidate (line starts with digit + period)
                if re.match(r'^\d+\.', line):
                    # Save previous section if exists
                    if current_section:
                        candidate_sections.append('\n'.join(current_section))
                    # Start new section
                    current_section = [line]
                else:
                    # Continue current section
                    current_section.append(line)

            # Parse each candidate section
            for section_text in candidate_sections:
                candidate = parse_viable_candidate(section_text, metadata)

                if candidate and 'symbol' in candidate:
                    asset = asset_manager.get_entity_from_database(candidate['symbol'])
                    if asset:
                        gap_result_id = insert_gap_result(cursor, candidate, asset.id)
                        print(f"  ✅ {candidate['symbol']}: gap_result_id={gap_result_id} (PASSED)")
                        saved_count += 1
                    else:
                        print(f"  ⚠️  {candidate['symbol']}: Not found in assets")

        # Find and parse failed candidates section
        failed_start = None
        for i, line in enumerate(lines):
            if "Top Candidates That Failed Volume Filter" in line:
                failed_start = i
                break

        if failed_start:
            # Parse failed candidates (compact format)
            i = failed_start + 4  # Skip header

            while i < len(lines):
                line = lines[i]

                # Stop at end marker
                if line.startswith("==="):
                    break

                # Check if this is a candidate line (starts with number)
                if re.match(r'^\d+\.', line):
                    # Collect this candidate's lines (usually 3 lines)
                    candidate_lines = [line]

                    # Get next 2 lines if they exist and are indented
                    if i + 1 < len(lines) and lines[i + 1].startswith('   '):
                        candidate_lines.append(lines[i + 1])
                    if i + 2 < len(lines) and lines[i + 2].startswith('   '):
                        candidate_lines.append(lines[i + 2])

                    # Parse this candidate
                    candidate = parse_multiline_failed_candidate(candidate_lines, metadata)

                    if candidate and 'symbol' in candidate:
                        asset = asset_manager.get_entity_from_database(candidate['symbol'])
                        if asset:
                            gap_result_id = insert_gap_result(cursor, candidate, asset.id)
                            print(f"  ✅ {candidate['symbol']}: gap_result_id={gap_result_id} (rejected)")
                            saved_count += 1
                        else:
                            print(f"  ⚠️  {candidate['symbol']}: Not found in assets")

                    # Skip the lines we just processed
                    i += len(candidate_lines)
                else:
                    i += 1

        conn.commit()

    return saved_count


def main():
    print("=" * 60)
    print("Gap Report Text Files Migration")
    print("=" * 60)

    db_manager = DatabaseManager()
    asset_manager = AssetManager(db_manager, None)

    # Find report files
    report_files = list(Path(".").glob("tradescout_gap_*.txt"))

    if not report_files:
        print("No report files found (tradescout_gap_*.txt)")
        return

    print(f"\nFound {len(report_files)} report file(s)")

    total_saved = 0

    for filepath in sorted(report_files):
        saved = process_report_file(filepath, db_manager, asset_manager)
        total_saved += saved

    print("\n" + "=" * 60)
    print(f"✅ Migration complete: {total_saved} gap results saved")
    print("=" * 60)

    # Show stats
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gap_results")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT trading_date) FROM gap_results")
        days = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM gap_results WHERE status='rejected'")
        rejected = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM gap_results WHERE status='passed' OR status='warning'")
        passed = cursor.fetchone()[0]

        print(f"\nDatabase: {count} total results across {days} trading days")
        print(f"  Passed/Warning: {passed}")
        print(f"  Rejected: {rejected}")


if __name__ == "__main__":
    main()
