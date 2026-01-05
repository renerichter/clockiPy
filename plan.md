# Implementation Plan for clockiPy Enhancements

## Phase 1: Add New Columns to Summary Tables
1. Write tests for the new columns in summary tables
   - Test that "Time by SubProject" table includes Meas<Plan and Meas>Plan columns
   - Test that "Time by Project" table includes Meas<Plan and Meas>Plan columns
   - Test that "Time by Tag" table includes Meas<Plan and Meas>Plan columns
   - Test that "Spontaneousity" table includes Meas<Plan and Meas>Plan columns

2. Implement the new columns in the summary tables
   - Update the `print_tables` function to calculate and display the new columns
   - Ensure percentages are displayed correctly
   - Update CSV export functionality for the new columns

## Phase 2: Create Comprehensive Tests
1. Set up a testing framework
   - Create a `tests` directory
   - Set up pytest configuration

2. Create mock data for testing
   - Mock API responses
   - Mock time entries with planned durations

3. Write unit tests for core functionality
   - Test parsing of planned durations from task names
   - Test calculation of duration differences
   - Test percentage calculations

4. Write integration tests
   - Test the complete workflow with mock data
   - Verify all tables contain the correct data and calculations

## Phase 3: Refactor Code
1. Restructure the project
   - Create a proper Python package structure
   - Separate concerns into different modules

2. Create core classes
   - `ClockifyClient` for API interactions
   - `TimeEntry` for representing and manipulating time entries
   - `ReportGenerator` for generating different reports

3. Implement utility modules
   - Date and time utilities
   - Formatting utilities
   - Configuration management

4. Refactor the CLI interface
   - Use a proper CLI framework
   - Implement subcommands for different functionalities

## Phase 4: Verification
1. Run all tests to ensure functionality is preserved
2. Manual verification of key features
   - Verify that all tables display correctly
   - Verify that the new columns show the correct values
   - Verify that CSV export works correctly

## Phase 5: Documentation
1. Update README.md with new features
2. Add docstrings to all new classes and functions
3. Create example usage documentation 