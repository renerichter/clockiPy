"""ReportGenerator class for generating reports from time entries."""
from datetime import date
from typing import List, Dict, Any, Tuple, DefaultDict, Optional
from collections import defaultdict
from tabulate import tabulate
from io import StringIO

from .time_entry import TimeEntry
from ..utils.format_utils import format_hm, percent

class ReportGenerator:
    """Class for generating reports from time entries."""
    
    def __init__(self, entries: List[TimeEntry], date_range_str: str, mode: str = "normal"):
        """Initialize a ReportGenerator.
        
        Args:
            entries: List of TimeEntry objects
            date_range_str: String representing the date range
            mode: Report mode (normal, week, month)
        """
        self.entries = entries
        self.date_range_str = date_range_str
        self.mode = mode
        
        # Calculate durations
        self.project_durations = defaultdict(int)
        self.tag_durations = defaultdict(int)
        self.spontaneousity_durations = {"🎲": 0, "🗓️": 0}
        self.total_duration = 0
        
        # Calculate planned vs. measured
        self.task_planned_measured = defaultdict(lambda: {"planned": 0, "measured": 0})
        self.task_occurrences = defaultdict(lambda: {"planned": 0, "measured": 0, "entries": []})
        self.occurrences = []
        self.plan_deviation_totals = {"over": 0, "under": 0, "abs": 0}
        
        # Process entries
        for entry in entries:
            self.total_duration += entry.duration_sec
            self.project_durations[entry.project_name] += entry.duration_sec
            
            for tag in entry.tag_names:
                self.tag_durations[tag] += entry.duration_sec
            
            if entry.is_spontaneous:
                self.spontaneousity_durations["🎲"] += entry.duration_sec
            elif entry.is_scheduled:
                self.spontaneousity_durations["🗓️"] += entry.duration_sec
            
            # Add to task planned vs. measured
            self.task_planned_measured[entry.description]["planned"] += entry.planned_sec
            self.task_planned_measured[entry.description]["measured"] += entry.duration_sec

            # Group occurrences (split recurring tasks by day)
            task_identity = (entry.description, entry.project_name, entry.task_name)
            occurrence_date = entry.start_date if entry.is_recurring else None
            occ_key = (task_identity, occurrence_date)
            occ_data = self.task_occurrences[occ_key]
            occ_data["planned"] += entry.planned_sec
            occ_data["measured"] += entry.duration_sec
            occ_data["entries"].append(entry)

        # Precomputed deviation allocations by dimension
        self.project_plan_diffs = defaultdict(lambda: {"less_plan": 0, "more_plan": 0})
        self.subproject_plan_diffs = defaultdict(lambda: {"less_plan": 0, "more_plan": 0})
        self.tag_plan_diffs = defaultdict(lambda: {"less_plan": 0, "more_plan": 0})
        self.spont_plan_diffs = defaultdict(lambda: {"less_plan": 0, "more_plan": 0})

        # Build occurrence summaries and deviation totals
        for (task_identity, occ_date), data in self.task_occurrences.items():
            description, project, task_name = task_identity
            planned = data["planned"]
            measured = data["measured"]
            diff = measured - planned if planned > 0 else 0
            occ_entries = data["entries"]
            self.occurrences.append({
                "description": description,
                "project": project,
                "task_name": task_name,
                "date": occ_date,
                "planned": planned,
                "measured": measured,
                "diff": diff,
                "entries": occ_entries,
            })

            if planned > 0:
                if diff > 0:
                    self.plan_deviation_totals["over"] += diff
                elif diff < 0:
                    self.plan_deviation_totals["under"] += abs(diff)
                self.plan_deviation_totals["abs"] += abs(diff)

                # Allocate to project
                if diff > 0:
                    self.project_plan_diffs[project]["more_plan"] += diff
                elif diff < 0:
                    self.project_plan_diffs[project]["less_plan"] += abs(diff)

                # Allocate to subproject
                subproject_key = (task_name, project)
                if diff > 0:
                    self.subproject_plan_diffs[subproject_key]["more_plan"] += diff
                elif diff < 0:
                    self.subproject_plan_diffs[subproject_key]["less_plan"] += abs(diff)

                # Allocate to spontaneity
                first_entry = occ_entries[0] if occ_entries else None
                if first_entry and (first_entry.is_spontaneous or first_entry.is_scheduled):
                    symbol = "🎲" if first_entry.is_spontaneous else "🗓️"
                    if diff > 0:
                        self.spont_plan_diffs[symbol]["more_plan"] += diff
                    elif diff < 0:
                        self.spont_plan_diffs[symbol]["less_plan"] += abs(diff)

                # Allocate to tags proportionally
                if diff != 0:
                    tag_durations = defaultdict(int)
                    total_occ_duration = 0
                    for entry in occ_entries:
                        total_occ_duration += entry.duration_sec
                        for tag in entry.tag_names:
                            tag_durations[tag] += entry.duration_sec

                    if tag_durations:
                        if total_occ_duration <= 0:
                            total_occ_duration = len(tag_durations)
                            for tag in tag_durations:
                                tag_durations[tag] = 1

                        abs_diff = abs(diff)
                        allocated_sum = 0
                        tag_list = list(tag_durations.items())
                        for i, (tag, tag_duration) in enumerate(tag_list):
                            if i == len(tag_list) - 1:
                                allocated = abs_diff - allocated_sum
                            else:
                                share = tag_duration / total_occ_duration
                                allocated = int(round(abs_diff * share))
                                allocated_sum += allocated
                            if diff > 0:
                                self.tag_plan_diffs[tag]["more_plan"] += allocated
                            else:
                                self.tag_plan_diffs[tag]["less_plan"] += allocated
    
    def generate_report(self, csv_prefix: Optional[str] = None, day_table: bool = False) -> str:
        """Generate a complete report.
        
        Args:
            csv_prefix: Prefix for CSV files (optional)
            day_table: Whether this is a day-specific table
            
        Returns:
            Report as a string
        """
        output = StringIO()
        
        # Generate tables
        self._generate_entries_table(output, csv_prefix, day_table)
        self._generate_subproject_table(output, csv_prefix)
        self._generate_project_table(output, csv_prefix)
        self._generate_tag_table(output, csv_prefix)
        self._generate_spontaneousity_table(output, csv_prefix)
        self._generate_totals_table(output, csv_prefix)
        
        return output.getvalue()
    
    def _generate_entries_table(self, output: StringIO, csv_prefix: Optional[str] = None, day_table: bool = False):
        """Generate the time entries table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
            day_table: Whether this is a day-specific table
        """
        if day_table is None:
            return  # Skip
        
        # Determine the correct percent header
        if day_table:
            percent_header = "%/Day"
        elif self.mode == "week":
            percent_header = "%/Week"
        elif self.mode == "month":
            percent_header = "%/Month"
        elif self.mode == "year":
            percent_header = "%/Year"
        else:
            percent_header = "%/Day"
        
        headers = ["#", "Task", "SubProject", "Project", "Planned", "Start", "End", "Duration", "Dur-Plan", "Tags", percent_header]
        
        # Create table rows
        table_rows = [entry.to_row(self.total_duration) for entry in self.entries]
        table_rows_with_ratio = [row[:-1] + [percent(row[-1], self.total_duration)] for row in table_rows]
        
        # Print table
        if day_table:
            print(f"\n### Time Entries {self.date_range_str}:", file=output)
        else:
            print(f"\n### Time Entries {self.date_range_str}:", file=output)
        
        print(tabulate(table_rows_with_ratio, headers=headers, tablefmt="github"), file=output)
        
        # Export to CSV if requested
        if csv_prefix:
            from ..utils.file_utils import write_csv
            write_csv(f"{csv_prefix}_entries.csv", headers, [row[:-1] + [percent(row[-1], self.total_duration)] for row in table_rows])
    
    def _generate_subproject_table(self, output: StringIO, csv_prefix: Optional[str] = None):
        """Generate the subproject table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
        """
        subproject_durations = defaultdict(int)
        
        for entry in self.entries:
            key = (entry.task_name, entry.project_name)
            subproject_durations[key] += entry.duration_sec
        
        if subproject_durations:
            if self.mode == "week":
                percent_header = "%/Week"
            elif self.mode == "month":
                percent_header = "%/Month"
            elif self.mode == "year":
                percent_header = "%/Year"
            else:
                percent_header = "%/Day"
            
            subproject_table = []
            for (subproject, project), secs in subproject_durations.items():
                more_plan = self.subproject_plan_diffs[(subproject, project)]["more_plan"]
                less_plan = self.subproject_plan_diffs[(subproject, project)]["less_plan"]
                more_plan_percent = percent(more_plan, secs) if secs > 0 else "0"
                less_plan_percent = percent(less_plan, secs) if secs > 0 else "0"
                
                subproject_table.append([
                    subproject, 
                    project, 
                    percent(secs, self.total_duration), 
                    more_plan_percent,
                    less_plan_percent,
                    format_hm(secs)
                ])
            
            def parse_duration_for_sort(duration_str):
                parts = duration_str.split(':')
                return int(parts[0]) * 60 + int(parts[1])
            
            subproject_table.sort(key=lambda x: parse_duration_for_sort(x[5]), reverse=True)
            print(f"\n### Time by SubProject {self.date_range_str}:", file=output)
            print(tabulate(subproject_table, headers=["SubProject", "Project", percent_header, "Meas>Plan%", "Meas<Plan%", "Duration"], tablefmt="github"), file=output)
            
            # Export to CSV if requested
            if csv_prefix:
                from ..utils.file_utils import write_csv
                write_csv(f"{csv_prefix}_subprojects.csv", ["SubProject", "Project", "%/Day", "Meas>Plan%", "Meas<Plan%", "Duration"], subproject_table)
    
    def _generate_project_table(self, output: StringIO, csv_prefix: Optional[str] = None):
        """Generate the project table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
        """
        if self.mode == "week":
            percent_header = "%/Week"
        elif self.mode == "month":
            percent_header = "%/Month"
        elif self.mode == "year":
            percent_header = "%/Year"
        else:
            percent_header = "%/Day"
        
        proj_table = []
        for proj, secs in sorted(self.project_durations.items(), key=lambda x: x[1], reverse=True):
            more_plan = self.project_plan_diffs[proj]["more_plan"]
            less_plan = self.project_plan_diffs[proj]["less_plan"]
            more_plan_percent = percent(more_plan, secs) if secs > 0 else "0"
            less_plan_percent = percent(less_plan, secs) if secs > 0 else "0"
            
            proj_table.append([
                proj, 
                percent(secs, self.total_duration), 
                more_plan_percent,
                less_plan_percent,
                format_hm(secs)
            ])
        
        print(f"\n### Time by Project {self.date_range_str}:", file=output)
        print(tabulate(proj_table, headers=["Project", percent_header, "Meas>Plan%", "Meas<Plan%", "Duration"], tablefmt="github"), file=output)
        
        # Export to CSV if requested
        if csv_prefix:
            from ..utils.file_utils import write_csv
            write_csv(f"{csv_prefix}_projects.csv", ["Project", percent_header, "Meas>Plan%", "Meas<Plan%", "Duration"], proj_table)
    
    def _generate_tag_table(self, output: StringIO, csv_prefix: Optional[str] = None):
        """Generate the tag table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
        """
        if not self.tag_durations:
            return
        
        if self.mode == "week":
            percent_header = "%/Week"
        elif self.mode == "month":
            percent_header = "%/Month"
        elif self.mode == "year":
            percent_header = "%/Year"
        else:
            percent_header = "%/Day"
        
        custom_tag_order = ["🚨 & 🍭", "🚨 & 🥵", "🐢 & 🍭", "🐢 & 🥵"]
        def tag_sort_key(item):
            tag = item[0]
            if tag in custom_tag_order:
                return (custom_tag_order.index(tag), tag)
            return (len(custom_tag_order), tag)
        
        tag_table = []
        for tag, secs in self.tag_durations.items():
            more_plan = self.tag_plan_diffs[tag]["more_plan"]
            less_plan = self.tag_plan_diffs[tag]["less_plan"]
            more_plan_percent = percent(more_plan, secs) if secs > 0 else "0"
            less_plan_percent = percent(less_plan, secs) if secs > 0 else "0"
            
            tag_table.append([
                tag, 
                percent(secs, self.total_duration), 
                more_plan_percent,
                less_plan_percent,
                format_hm(secs)
            ])
        
        tag_table.sort(key=tag_sort_key)
        print(f"\n### Time by Tag {self.date_range_str}:", file=output)
        print(tabulate(tag_table, headers=["Tag", percent_header, "Meas>Plan%", "Meas<Plan%", "ΣDuration"], tablefmt="github"), file=output)
        
        # Export to CSV if requested
        if csv_prefix:
            from ..utils.file_utils import write_csv
            write_csv(f"{csv_prefix}_tags.csv", ["Tag", percent_header, "Meas>Plan%", "Meas<Plan%", "ΣDuration"], tag_table)
    
    def _generate_spontaneousity_table(self, output: StringIO, csv_prefix: Optional[str] = None):
        """Generate the spontaneity table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
        """
        spont_total = sum(self.spontaneousity_durations.values())
        if spont_total == 0:
            return
        
        if self.mode == "week":
            percent_header = "%/Week"
        elif self.mode == "month":
            percent_header = "%/Month"
        elif self.mode == "year":
            percent_header = "%/Year"
        else:
            percent_header = "%/Day"
        
        spont_order = ["🗓️", "🎲"]
        spont_table = []
        
        for symbol, secs in self.spontaneousity_durations.items():
            if secs > 0:
                more_plan = self.spont_plan_diffs[symbol]["more_plan"]
                less_plan = self.spont_plan_diffs[symbol]["less_plan"]
                more_plan_percent = percent(more_plan, secs) if secs > 0 else "0"
                less_plan_percent = percent(less_plan, secs) if secs > 0 else "0"
                
                spont_table.append([
                    symbol, 
                    percent(secs, spont_total), 
                    more_plan_percent,
                    less_plan_percent,
                    format_hm(secs)
                ])
        
        spont_table.sort(key=lambda row: spont_order.index(row[0]) if row[0] in spont_order else len(spont_order))
        print(f"\n### Spontaneousity {self.date_range_str}:", file=output)
        print(tabulate(spont_table, headers=["🎲/🗓️", percent_header, "Meas>Plan%", "Meas<Plan%", "Duration"], tablefmt="github"), file=output)
        
        # Export to CSV if requested
        if csv_prefix:
            from ..utils.file_utils import write_csv
            write_csv(f"{csv_prefix}_spont.csv", ["🎲/🗓️", percent_header, "Meas>Plan%", "Meas<Plan%", "Duration"], spont_table)
    
    def _generate_totals_table(self, output: StringIO, csv_prefix: Optional[str] = None):
        """Generate the totals table.
        
        Args:
            output: StringIO to write to
            csv_prefix: Prefix for CSV files (optional)
        """
        over_plan_total = self.plan_deviation_totals["over"]
        under_plan_total = self.plan_deviation_totals["under"]
        abs_diff_total = self.plan_deviation_totals["abs"]
        
        totals_table = []
        totals_table.append(["ΣDuration", "0%", format_hm(self.total_duration)])
        
        over_plan_str = format_hm(over_plan_total)
        under_plan_str = format_hm(under_plan_total)
        abs_diff_str = format_hm(abs_diff_total)
        
        over_plan_pct = f"{(over_plan_total / self.total_duration * 100):.0f}%" if self.total_duration else "0%"
        under_plan_pct = f"{(under_plan_total / self.total_duration * 100):.0f}%" if self.total_duration else "0%"
        abs_diff_pct = f"{(abs_diff_total / self.total_duration * 100):.0f}%" if self.total_duration else "0%"
        
        totals_table.append(["Meas>Plan Total", over_plan_pct, over_plan_str])
        totals_table.append(["Meas<Plan Total", under_plan_pct, under_plan_str])
        totals_table.append(["Abs(Dur-Plan) Total", abs_diff_pct, abs_diff_str])
        
        print(f"\n### Totals {self.date_range_str}:", file=output)
        print(tabulate(totals_table, headers=["Total", "Dev (%)", "Abs (h:mm)"], tablefmt="github"), file=output)
        
        # Export to CSV if requested
        if csv_prefix:
            from ..utils.file_utils import write_csv
            write_csv(f"{csv_prefix}_totals.csv", ["Total", "% Dev", "h:mm"], totals_table)
        
        print(file=output)  # Extra newline 
