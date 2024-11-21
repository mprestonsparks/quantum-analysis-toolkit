import os
import json
import subprocess
import datetime
import shutil
import cmd
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum, auto
import argparse
from pathlib import Path
import textwrap
from colorama import init, Fore, Style  # For colored output

# Initialize colorama for Windows support
init()

class FileStatus(Enum):
    PENDING = "pending"
    TESTS_WRITTEN = "tests_written"
    TESTS_REVIEWED = "tests_reviewed"
    CODE_IMPLEMENTED = "code_implemented"
    CODE_REVIEWED = "code_reviewed"
    COMPLETED = "completed"

class ScenarioLevel(Enum):
    BASIC = "basic"                # Scenario 1
    INTERMEDIATE = "intermediate"  # Scenario 2
    ADVANCED = "advanced"          # Scenario 3

class WorkflowState(Enum):
    PENDING = auto()                     # Initial state
    ISSUE_CREATED = auto()               # GitHub issue exists
    TESTS_PROVIDED = auto()              # Claude provided tests
    TESTS_REVIEWED = auto()              # You reviewed tests
    IMPLEMENTATION_PROVIDED = auto()      # Claude provided implementation
    IMPLEMENTATION_REVIEWED = auto()      # You reviewed implementation
    DOCUMENTATION_PROVIDED = auto()       # Claude provided documentation
    DOCUMENTATION_REVIEWED = auto()       # You reviewed documentation
    EXAMPLES_PROVIDED = auto()            # Claude provided examples
    EXAMPLES_REVIEWED = auto()            # You reviewed examples
    COMPLETED = auto()                   # All steps completed

@dataclass
class WorkflowTracker:
    source_file: str
    test_file: str
    example_file: Optional[str]
    status: FileStatus
    scenario: ScenarioLevel
    workflow_state: WorkflowState
    issue_number: Optional[str]
    last_updated: str
    notes: List[str]
    dependencies: List[str]
    acceptance_criteria: List[str]
    test_review_comments: List[str]
    implementation_review_comments: List[str]
    documentation_review_comments: List[str]
    examples_review_comments: List[str]

class QToolsProject:
    """Defines the qtools project structure and dependencies"""
    
    def __init__(self):
        # Define all project files with their dependencies
        self.files = {
            # Scenario 1 - Basic
            "src/utils/types.rs": {
                "test_file": "tests/utils/types_tests.rs",
                "example_file": "examples/types_usage.rs",
                "scenario": ScenarioLevel.BASIC,
                "dependencies": [],
                "description": "Core data structures for time series and market data"
            },
            "src/signal/weak_signal.rs": {
                "test_file": "tests/signal/weak_signal_tests.rs",
                "example_file": "examples/signal_analysis.rs",
                "scenario": ScenarioLevel.BASIC,
                "dependencies": ["src/utils/types.rs"],
                "description": "Weak signal detection and filtering"
            },
            "src/pattern/recognition.rs": {
                "test_file": "tests/pattern/recognition_tests.rs",
                "example_file": "examples/pattern_detection.rs",
                "scenario": ScenarioLevel.BASIC,
                "dependencies": ["src/utils/types.rs"],
                "description": "Basic pattern recognition algorithms"
            },
            
            # Scenario 2 - Intermediate
            "src/quantum/state.rs": {
                "test_file": "tests/quantum/state_tests.rs",
                "example_file": "examples/quantum_state.rs",
                "scenario": ScenarioLevel.INTERMEDIATE,
                "dependencies": ["src/utils/types.rs", "src/signal/weak_signal.rs"],
                "description": "Quantum state representation and analysis"
            },
            "src/sync/phase.rs": {
                "test_file": "tests/sync/phase_tests.rs",
                "example_file": "examples/phase_sync.rs",
                "scenario": ScenarioLevel.INTERMEDIATE,
                "dependencies": ["src/quantum/state.rs"],
                "description": "Phase synchronization detection"
            },
            
            # Scenario 3 - Advanced
            "src/network/kuramoto.rs": {
                "test_file": "tests/network/kuramoto_tests.rs",
                "example_file": "examples/kuramoto_model.rs",
                "scenario": ScenarioLevel.ADVANCED,
                "dependencies": ["src/quantum/state.rs", "src/sync/phase.rs"],
                "description": "Kuramoto model implementation for network synchronization"
            },
            "src/network/topology.rs": {
                "test_file": "tests/network/topology_tests.rs",
                "example_file": "examples/network_topology.rs",
                "scenario": ScenarioLevel.ADVANCED,
                "dependencies": ["src/network/kuramoto.rs"],
                "description": "Network topology analysis"
            },
            "src/quantum/entanglement.rs": {
                "test_file": "tests/quantum/entanglement_tests.rs",
                "example_file": "examples/entanglement.rs",
                "scenario": ScenarioLevel.ADVANCED,
                "dependencies": ["src/quantum/state.rs"],
                "description": "Quantum entanglement measures"
            }
        }

        # Template content for different file types
        self.templates = {
            "source": textwrap.dedent("""
                //! {description}
                
                use crate::utils::types::*;
                
                /// Main struct for {filename} functionality
                pub struct {struct_name} {{
                    // TODO: Add fields
                }}
                
                impl {struct_name} {{
                    /// Creates a new instance
                    pub fn new() -> Self {{
                        Self {{
                            // TODO: Initialize fields
                        }}
                    }}
                    
                    // TODO: Add methods
                }}
            """).strip(),
            
            "test": textwrap.dedent("""
                use super::*;
                use crate::utils::types::*;
                
                #[test]
                fn test_{struct_name}_creation() {{
                    let instance = {struct_name}::new();
                    // TODO: Add assertions
                }}
                
                // TODO: Add more tests
            """).strip(),
            
            "mod": textwrap.dedent("""
                //! Module for {description}
                
                mod {module_name};
                pub use {module_name}::*;
            """).strip(),
            
            "example": textwrap.dedent("""
                use qtools::*;
                
                fn main() {{
                    // Example usage of {struct_name}
                    let instance = {struct_name}::new();
                    
                    // TODO: Add example usage
                }}
            """).strip(),
        }

class QToolsWorkflowHelper:
    """Defines the workflow helper for the qtools project"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.workflow_file = self.project_root / ".workflow_status.json"
        self.workflow_status: Dict[str, WorkflowTracker] = {}
        self.project = QToolsProject()
        
        # Define the standard workflow sequence with method references
        self.workflow_sequence = {
            WorkflowState.PENDING: (
                "Create GitHub Issue",
                self.get_issue_creation_instructions
            ),
            WorkflowState.ISSUE_CREATED: (
                "Get Tests from Claude",
                self.get_test_request_instructions
            ),
            WorkflowState.TESTS_PROVIDED: (
                "Review Tests",
                self.get_test_review_instructions
            ),
            WorkflowState.TESTS_REVIEWED: (
                "Get Implementation from Claude",
                self.get_implementation_request_instructions
            ),
            WorkflowState.IMPLEMENTATION_PROVIDED: (
                "Review Implementation",
                self.get_implementation_review_instructions
            ),
            WorkflowState.IMPLEMENTATION_REVIEWED: (
                "Get Documentation from Claude",
                self.get_documentation_request_instructions
            ),
            WorkflowState.DOCUMENTATION_PROVIDED: (
                "Review Documentation",
                self.get_documentation_review_instructions
            ),
            WorkflowState.DOCUMENTATION_REVIEWED: (
                "Get Examples from Claude",
                self.get_examples_request_instructions
            ),
            WorkflowState.EXAMPLES_PROVIDED: (
                "Review Examples",
                self.get_examples_review_instructions
            ),
            WorkflowState.EXAMPLES_REVIEWED: (
                "Component Development Completed",
                self.get_completion_instructions
            ),
        }

        # Define scenario 1 files in order
        self.scenario_1_sequence = [
            ("src/utils/types.rs", "tests/utils/types_tests.rs", "examples/types_usage.rs"),
            ("src/signal/weak_signal.rs", "tests/signal/weak_signal_tests.rs", "examples/signal_analysis.rs"),
            ("src/pattern/recognition.rs", "tests/pattern/recognition_tests.rs", "examples/pattern_detection.rs"),
            ("examples/basic_trading.rs", None, None)
        ]

        self.load_workflow_status()

    def load_workflow_status(self):
        """Load workflow status from JSON file"""
        if self.workflow_file.exists():
            with open(self.workflow_file) as f:
                data = json.load(f)
                self.workflow_status = {
                    k: WorkflowTracker(
                        **{**v, 
                           'status': FileStatus(v['status']),
                           'scenario': ScenarioLevel(v['scenario']),
                           'workflow_state': WorkflowState[v['workflow_state']]
                        })
                    for k, v in data.items()
                }
        else:
            # Initialize workflow status from project files
            for source_file, info in self.project.files.items():
                self.workflow_status[source_file] = WorkflowTracker(
                    source_file=source_file,
                    test_file=info["test_file"],
                    example_file=info.get("example_file"),
                    status=FileStatus.PENDING,
                    scenario=info["scenario"],
                    workflow_state=WorkflowState.PENDING,
                    issue_number=None,
                    last_updated=datetime.datetime.now().isoformat(),
                    notes=[],
                    dependencies=info["dependencies"],
                    acceptance_criteria=[],
                    test_review_comments=[],
                    implementation_review_comments=[],
                    documentation_review_comments=[],
                    examples_review_comments=[]
                )
            self.save_workflow_status()

    def save_workflow_status(self):
        """Save workflow status to JSON file"""
        with open(self.workflow_file, 'w') as f:
            json.dump({
                k: {**asdict(v), 
                    'status': v.status.value,
                    'scenario': v.scenario.value,
                    'workflow_state': v.workflow_state.name
                }
                for k, v in self.workflow_status.items()
            }, f, indent=2)

    def get_next_task(self) -> Optional[Tuple[str, List[str]]]:
        """Get the next file to work on based on dependencies"""
        for source_file, tracker in self.workflow_status.items():
            if tracker.workflow_state != WorkflowState.COMPLETED:
                # Check if all dependencies are completed
                deps_completed = all(
                    self.workflow_status[dep].workflow_state == WorkflowState.COMPLETED
                    for dep in tracker.dependencies
                )
                if deps_completed:
                    return source_file, tracker.dependencies
        return None

    def get_current_file(self) -> Optional[str]:
        """Get the current file being worked on"""
        next_task = self.get_next_task()
        return next_task[0] if next_task else None

    def format_instruction_header(self, title: str) -> str:
        """Format section header with color"""
        return f"\n{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}\n"

    def format_instruction_step(self, step: str) -> str:
        """Format instruction step with color"""
        return f"{Fore.GREEN}•{Style.RESET_ALL} {step}"

    def get_issue_creation_instructions(self, file: str) -> str:
        """Get instructions for creating a GitHub issue"""
        tracker = self.workflow_status[file]
        dependencies_text = "\n".join(
            f"  {Fore.YELLOW}•{Style.RESET_ALL} {dep}" 
            for dep in tracker.dependencies
        ) if tracker.dependencies else f"  {Fore.YELLOW}None{Style.RESET_ALL}"

        return (
            f"{self.format_instruction_header('Create GitHub Issue')}\n"
            f"{self.format_instruction_step('Component: ' + file)}\n"
            f"{self.format_instruction_step('Description: ' + self.project.files[file]['description'])}\n\n"
            f"{self.format_instruction_header('Required Sections')}\n"
            f"{self.format_instruction_step('Component Purpose')}\n"
            f"{self.format_instruction_step('Acceptance Criteria')}\n"
            f"{self.format_instruction_step('Expected Interfaces')}\n"
            f"{self.format_instruction_step('Performance Requirements')}\n"
            f"{self.format_instruction_step('Error Handling Requirements')}\n\n"
            f"{self.format_instruction_header('Dependencies')}\n"
            f"{dependencies_text}"
        )

    # ... Include the rest of the instruction methods with similar formatting ...

    def record_issue(self, issue_number: str):
        """Record that a GitHub issue was created"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.issue_number = issue_number
        tracker.workflow_state = WorkflowState.ISSUE_CREATED
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.GREEN}Recorded issue #{issue_number} for {current_file}{Style.RESET_ALL}")
        return True

    def record_tests(self):
        """Record that Claude provided tests"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.workflow_state = WorkflowState.TESTS_PROVIDED
        tracker.status = FileStatus.TESTS_WRITTEN
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.GREEN}Recorded test receipt for {current_file}{Style.RESET_ALL}")
        return True

    def approve_tests(self, comment: Optional[str] = None):
        """Record that tests were approved"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.workflow_state = WorkflowState.TESTS_REVIEWED
        tracker.status = FileStatus.TESTS_REVIEWED
        if comment:
            tracker.test_review_comments.append(comment)
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.GREEN}Recorded test approval for {current_file}{Style.RESET_ALL}")
        return True

    def request_test_changes(self, comment: str):
        """Record that test changes were requested"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.workflow_state = WorkflowState.ISSUE_CREATED  # Go back to get new tests
        tracker.test_review_comments.append(comment)
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.YELLOW}Requested test changes for {current_file}{Style.RESET_ALL}")
        print(f"Comment: {comment}")
        return True

    def record_implementation(self):
        """Record that Claude provided implementation"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.workflow_state = WorkflowState.IMPLEMENTATION_PROVIDED
        tracker.status = FileStatus.CODE_IMPLEMENTED
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.GREEN}Recorded implementation receipt for {current_file}{Style.RESET_ALL}")
        return True

    def approve_implementation(self, comment: Optional[str] = None):
        """Record that implementation was approved"""
        current_file = self.get_current_file()
        if not current_file:
            print(f"{Fore.RED}No current file to work on{Style.RESET_ALL}")
            return False
            
        tracker = self.workflow_status[current_file]
        tracker.workflow_state = WorkflowState.IMPLEMENTATION_REVIEWED
        tracker.status = FileStatus.CODE_REVIEWED
        if comment:
            tracker.implementation_review_comments.append(comment)
        tracker.last_updated = datetime.datetime.now().isoformat()
        self.save_workflow_status()
        
        print(f"{Fore.GREEN}Recorded implementation approval for {current_file}{Style.RESET_ALL}")
        return True

    def run_tests(self, specific_file: Optional[str] = None):
        """Run cargo tests for specific file or all files"""
        os.chdir(self.project_root)
        file_to_test = specific_file or self.get_current_file()
        
        if file_to_test:
            test_file = self.workflow_status[file_to_test].test_file
            cmd = ["cargo", "test", "--test", Path(test_file).stem]
        else:
            cmd = ["cargo", "test"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"\n{Fore.CYAN}Test Results:{Style.RESET_ALL}")
            print(result.stdout)
            if result.stderr:
                print(f"\n{Fore.RED}Errors:{Style.RESET_ALL}")
                print(result.stderr)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"{Fore.RED}Error running tests: {e}{Style.RESET_ALL}")
            return False

    def show_progress(self):
        """Display detailed progress through Scenario 1"""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}Scenario 1 Progress:{Style.RESET_ALL}\n")
        
        for source, test, example in self.scenario_1_sequence:
            tracker = self.workflow_status.get(source)
            if not tracker:
                print(f"{source}: {Fore.RED}Not started{Style.RESET_ALL}")
                continue

            state_color = Fore.GREEN if tracker.workflow_state == WorkflowState.COMPLETED else Fore.YELLOW
            print(f"\n{Fore.BLUE}{source}:{Style.RESET_ALL}")
            print(f"  Current State: {state_color}{tracker.workflow_state.name}{Style.RESET_ALL}")
            print(f"  Last Updated: {tracker.last_updated}")
            
            if tracker.issue_number:
                print(f"  Issue: #{tracker.issue_number}")
            if tracker.notes:
                print(f"  Latest Note: {tracker.notes[-1]}")
            if tracker.test_review_comments:
                print(f"  Latest Test Review: {tracker.test_review_comments[-1]}")
            if tracker.implementation_review_comments:
                print(f"  Latest Implementation Review: {tracker.implementation_review_comments[-1]}")

        next_action, _ = self.get_next_action()
        print(f"\n{Fore.GREEN}Next Action: {next_action}{Style.RESET_ALL}")

    def get_next_action(self) -> Tuple[str, str]:
        """Get the next action needed in the workflow"""
        current_file = self.get_current_file()
        if not current_file:
            return "All Scenario 1 files completed!", ""

        tracker = self.workflow_status[current_file]
        action_name, instruction_getter = self.workflow_sequence[tracker.workflow_state]
        instructions = instruction_getter(current_file)

        return action_name, instructions

    def get_test_request_instructions(self, file: str) -> str:
        """Get instructions for requesting tests from Claude"""
        tracker = self.workflow_status[file]
        return (
            f"{self.format_instruction_header('Request Tests from Claude')}\n"
            f"{self.format_instruction_step(f'Component: {file}')}\n"
            f"{self.format_instruction_step('Provide the GitHub issue link to Claude.')}\n"
            f"{self.format_instruction_step('Ask Claude to write unit tests based on the issue details and acceptance criteria.')}\n"
            f"{self.format_instruction_step('Ensure that the tests cover all edge cases.')}"
        )

    def get_test_review_instructions(self, file: str) -> str:
        """Get instructions for reviewing tests"""
        return (
            f"{self.format_instruction_header('Review Tests')}\n"
            f"{self.format_instruction_step('Review the tests provided by Claude.')}\n"
            f"{self.format_instruction_step('Run the tests to ensure they pass or fail appropriately.')}\n"
            f"{self.format_instruction_step('Check for coverage of acceptance criteria and edge cases.')}\n"
            f"{self.format_instruction_step('Provide feedback or approve the tests.')}"
        )

    def get_implementation_request_instructions(self, file: str) -> str:
        """Get instructions for requesting implementation from Claude"""
        return (
            f"{self.format_instruction_header('Request Implementation from Claude')}\n"
            f"{self.format_instruction_step('Inform Claude that the tests have been approved.')}\n"
            f"{self.format_instruction_step('Ask Claude to implement the component to pass the tests.')}\n"
            f"{self.format_instruction_step('Request adherence to coding standards and best practices.')}"
        )

    def get_implementation_review_instructions(self, file: str) -> str:
        """Get instructions for reviewing the implementation"""
        return (
            f"{self.format_instruction_header('Review Implementation')}\n"
            f"{self.format_instruction_step('Review the code for correctness and style.')}\n"
            f"{self.format_instruction_step('Run the tests to ensure all pass.')}\n"
            f"{self.format_instruction_step('Check for performance and resource usage.')}\n"
            f"{self.format_instruction_step('Provide feedback or approve the implementation.')}"
        )

    def get_documentation_request_instructions(self, file: str) -> str:
        """Get instructions for requesting documentation from Claude"""
        return (
            f"{self.format_instruction_header('Request Documentation from Claude')}\n"
            f"{self.format_instruction_step('Ask Claude to write comprehensive documentation for the component.')}\n"
            f"{self.format_instruction_step('Include usage examples and explanations of parameters and return values.')}"
        )

    def get_documentation_review_instructions(self, file: str) -> str:
        """Get instructions for reviewing the documentation"""
        return (
            f"{self.format_instruction_header('Review Documentation')}\n"
            f"{self.format_instruction_step('Review the documentation for clarity and completeness.')}\n"
            f"{self.format_instruction_step('Ensure that all functions and methods are documented.')}\n"
            f"{self.format_instruction_step('Provide feedback or approve the documentation.')}"
        )

    def get_examples_request_instructions(self, file: str) -> str:
        """Get instructions for requesting examples from Claude"""
        return (
            f"{self.format_instruction_header('Request Examples from Claude')}\n"
            f"{self.format_instruction_step('Ask Claude to provide example code demonstrating typical usage scenarios.')}\n"
            f"{self.format_instruction_step('Ensure examples are practical and cover common use cases.')}"
        )

    def get_examples_review_instructions(self, file: str) -> str:
        """Get instructions for reviewing the examples"""
        return (
            f"{self.format_instruction_header('Review Examples')}\n"
            f"{self.format_instruction_step('Review the provided examples for accuracy and usefulness.')}\n"
            f"{self.format_instruction_step('Test the examples to ensure they work as intended.')}\n"
            f"{self.format_instruction_step('Provide feedback or approve the examples.')}"
        )

    def get_completion_instructions(self, file: str) -> str:
        """Get instructions upon component completion"""
        return (
            f"{self.format_instruction_header('Component Development Completed')}\n"
            f"{self.format_instruction_step(f'Congratulations! Development of {file} is complete.')}\n"
            f"{self.format_instruction_step('Proceed to the next component in the workflow.')}"
        )

class QToolsPrompt(cmd.Cmd):
    intro = f"""
    {Fore.CYAN}{Style.BRIGHT}QTools TDD Helper - Interactive Development Workflow{Style.RESET_ALL}
    Type {Fore.GREEN}'help'{Style.RESET_ALL} or {Fore.GREEN}'?'{Style.RESET_ALL} to list commands.
    Type {Fore.GREEN}'quit'{Style.RESET_ALL} or {Fore.GREEN}'exit'{Style.RESET_ALL} to exit.
    """
    prompt = f"{Fore.GREEN}qtools>{Style.RESET_ALL} "

    def __init__(self, project_root: str):
        super().__init__()
        self.helper = QToolsWorkflowHelper(project_root)
        self.current_file = None
        # Show initial status
        self.do_status("")

    def do_init(self, arg):
        """Initialize the project structure"""
        self.helper.initialize_project()
        print(f"\n{Fore.GREEN}Project initialized. Getting next action...{Style.RESET_ALL}")
        self.do_next("")

    def do_next(self, arg):
        """Show the next action needed in the workflow"""
        action, instructions = self.helper.get_next_action()
        print(f"\n{Fore.CYAN}Next Action: {action}{Style.RESET_ALL}")
        print("\nInstructions:")
        print(instructions)
        
        # Guide user to the next command
        if action == "Create GitHub Issue":
            print(f"\nTo record the issue, type: {Fore.GREEN}issue <number>{Style.RESET_ALL}")
        elif action == "Get Tests from Claude":
            print(f"\nAfter receiving tests from Claude, type: {Fore.GREEN}tests-received{Style.RESET_ALL}")
        elif action == "Review Tests":
            print(f"\nAfter review, type: {Fore.GREEN}approve-tests{Style.RESET_ALL} or {Fore.GREEN}request-test-changes{Style.RESET_ALL}")
        elif action == "Get Implementation from Claude":
            print(f"\nAfter receiving implementation, type: {Fore.GREEN}implementation-received{Style.RESET_ALL}")
        elif action == "Review Implementation":
            print(f"\nAfter review, type: {Fore.GREEN}approve-implementation{Style.RESET_ALL} or {Fore.GREEN}request-implementation-changes{Style.RESET_ALL}")

    def do_issue(self, arg):
        """Record a GitHub issue number for the current task
        Usage: issue <number>"""
        if not arg:
            print(f"{Fore.RED}Please provide the issue number. Usage: issue <number>{Style.RESET_ALL}")
            return
        
        action, _ = self.helper.get_next_action()
        if action != "Create GitHub Issue":
            print(f"{Fore.RED}Current step is not issue creation. Type 'next' to see current step.{Style.RESET_ALL}")
            return

        if self.helper.record_issue(arg):
            self.do_next("")

    def do_tests_received(self, arg):
        """Record that Claude has provided tests"""
        if self.helper.record_tests():
            print(f"\n{Fore.CYAN}Do you want to review the tests now? (yes/no){Style.RESET_ALL}")
            if input().lower().startswith('y'):
                self.do_run_tests("")
            else:
                self.do_next("")

    def do_run_tests(self, arg):
        """Run the tests for the current component"""
        success = self.helper.run_tests()
        if success:
            print(f"\n{Fore.GREEN}Tests passed!{Style.RESET_ALL}")
            print(f"Type {Fore.CYAN}approve-tests{Style.RESET_ALL} to approve or {Fore.CYAN}request-test-changes{Style.RESET_ALL} to request changes.")
        else:
            print(f"\n{Fore.YELLOW}Tests failed.{Style.RESET_ALL}")
            print(f"Type {Fore.CYAN}request-test-changes{Style.RESET_ALL} to request changes from Claude.")

    def do_approve_tests(self, arg):
        """Approve the current tests"""
        print(f"{Fore.CYAN}Optional approval comment:{Style.RESET_ALL}")
        comment = input().strip() or None
        if self.helper.approve_tests(comment):
            self.do_next("")

    def do_request_test_changes(self, arg):
        """Request changes to the current tests"""
        print(f"{Fore.CYAN}What changes are needed?{Style.RESET_ALL}")
        comment = input().strip()
        if not comment:
            print(f"{Fore.RED}Please provide a comment explaining the needed changes.{Style.RESET_ALL}")
            return
        if self.helper.request_test_changes(comment):
            self.do_next("")

    def do_implementation_received(self, arg):
        """Record that Claude has provided implementation"""
        if self.helper.record_implementation():
            print(f"\n{Fore.CYAN}Do you want to run the tests now? (yes/no){Style.RESET_ALL}")
            if input().lower().startswith('y'):
                self.do_run_tests("")
            else:
                self.do_next("")

    def do_approve_implementation(self, arg):
        """Approve the current implementation"""
        print(f"{Fore.CYAN}Optional approval comment:{Style.RESET_ALL}")
        comment = input().strip() or None
        if self.helper.approve_implementation(comment):
            self.do_next("")

    def do_request_implementation_changes(self, arg):
        """Request changes to the current implementation"""
        print(f"{Fore.CYAN}What changes are needed?{Style.RESET_ALL}")
        comment = input().strip()
        if not comment:
            print(f"{Fore.RED}Please provide a comment explaining the needed changes.{Style.RESET_ALL}")
            return
        if self.helper.request_implementation_changes(comment):
            self.do_next("")

    def do_status(self, arg):
        """Show current project status"""
        self.helper.show_progress()

    def do_help(self, arg):
        """Show help message"""
        if arg:
            # Show help for specific command
            super().do_help(arg)
        else:
            # Show general help
            print(f"\n{Fore.CYAN}{Style.BRIGHT}Available Commands:{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}next{Style.RESET_ALL}                     - Show next action needed")
            print(f"  {Fore.GREEN}status{Style.RESET_ALL}                   - Show project status")
            print(f"  {Fore.GREEN}issue <number>{Style.RESET_ALL}           - Record GitHub issue")
            print(f"  {Fore.GREEN}tests-received{Style.RESET_ALL}           - Record test receipt")
            print(f"  {Fore.GREEN}run-tests{Style.RESET_ALL}                - Run current tests")
            print(f"  {Fore.GREEN}approve-tests{Style.RESET_ALL}            - Approve current tests")
            print(f"  {Fore.GREEN}request-test-changes{Style.RESET_ALL}     - Request test changes")
            print(f"  {Fore.GREEN}implementation-received{Style.RESET_ALL}  - Record implementation")
            print(f"  {Fore.GREEN}approve-implementation{Style.RESET_ALL}   - Approve implementation")
            print(f"  {Fore.GREEN}help{Style.RESET_ALL}                     - Show this help message")
            print(f"  {Fore.GREEN}quit{Style.RESET_ALL}                     - Exit the program")

    def do_quit(self, arg):
        """Exit the program"""
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
        return True

    def do_exit(self, arg):
        """Exit the program"""
        return self.do_quit(arg)

    def default(self, line):
        """Handle unknown commands"""
        print(f"{Fore.RED}Unknown command: {line}{Style.RESET_ALL}")
        print(f"Type {Fore.GREEN}'help'{Style.RESET_ALL} or {Fore.GREEN}'?'{Style.RESET_ALL} to see available commands.")

    def emptyline(self):
        """Don't repeat last command on empty line"""
        self.do_next("")

# Dedent the main() function to the module level
def main():
    parser = argparse.ArgumentParser(description="QTools TDD Helper")
    parser.add_argument("--project-root", default=".",
                        help="Root directory of the qtools project (default: current directory)")

    args = parser.parse_args()

    try:
        # Create project directory if it doesn't exist
        project_path = Path(args.project_root)
        project_path.mkdir(parents=True, exist_ok=True)

        # Start interactive prompt
        prompt = QToolsPrompt(args.project_root)
        prompt.cmdloop()
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        sys.exit(1)

# Ensure this is at the end of your file
if __name__ == "__main__":
    main()
