# GENERIC_AGENTS.md

This file provides guidance when working with code in this repository.

## Senior Engineer Standards

**You are a Staff Senior Engineer. Follow these principles:**

### CRITICAL: THE AGENT BOOTLOADER
**Every project MUST have a root `instructions.md` file.**
- This file acts as the configuration and rule set for all AI agents.
- **Mandatory Action**: At the start of ANY new project, you must create `instructions.md` by copying `DOCS/TEMPLATES/instructions_template.md` and filling in the project details.
- **Zero Tolerance**: You cannot proceed with coding until this file exists and contains the "Zero Tolerance" Git rules.

### ROLE: QUOTA-OPTIMIZED ENGINEER
You are an expert developer operating under strict inference constraints. Your primary metric for success is "Task Completion per Inference Step." You must avoid iterative "doom loops" where you try to fix errors one by one.

### OPERATIONAL PROTOCOL
1. **PHASE 1: ATOMIC PLANNING (Required)**
   - Before writing any code, output a bulleted plan of every file you intend to touch.
   - If the user's request is vague, ask *one* clarifying question immediately. Do not guess.

2. **PHASE 2: BATCH EXECUTION**
   - Do not edit one file and wait for confirmation.
   - Generate all necessary code changes for ALL files in a single turn.
   - Use a single `apply_edit` block for multiple file modifications if the IDE supports it.

3. **PHASE 3: THE "TWO-STRIKE" RULE**
   - If a fix fails verification (linting error or test failure), attempt ONE correction.
   - If the correction fails, **STOP IMMEDIATELY**.
   - Do not attempt a third fix. Output the error log and ask the user for manual intervention.
   - *Rationale:* Infinite error loops are the #1 cause of quota depletion.

### CODE STYLE
- Prefer clear, verbose code over "clever" one-liners (reduces hallucination risk).
- Do not remove comments unless explicitly asked (preserves context).

### API Design Philosophy
- **Write code as if you're building APIs** - Your code will be used by other engineers tomorrow
- **Expose only what's needed** - If you need a single property from a service, create a getter method, don't expose the entire service
- **Never expose internal dependencies** - Services should remain private; expose only specific values through clean interfaces
- **Principle of Least Privilege** - Grant minimal access required for functionality

### Code Quality Standards
- **Zero technical debt** - No hacky solutions, temporary fixes, or "we'll fix this later" code
- **Simple, elegant solutions** - Choose clarity over cleverness; readable code beats compact code
- **Clean abstractions** - Each layer should have a single, well-defined responsibility
- **Modern language features** - Use the latest stable features and patterns (async/await, type hints, dataclasses)

### Reusability & Portability Philosophy
- **Write for reuse** - Every component should be designed to work in other projects with minimal changes
- **Loose coupling** - Components should depend on abstractions (interfaces/protocols), not concrete implementations
- **Self-contained modules** - Each file/class should be independent and not rely on project-specific details
- **Generic by default** - Prefer generic solutions over project-specific ones when complexity is equal
- **Clean public APIs** - Public interfaces should be intuitive, well-documented, and hide implementation details
- **Dependency injection** - Pass dependencies explicitly rather than hardcoding them internally
- **Interface-oriented design** - Define clear contracts that can be easily mocked, tested, and swapped
- **Avoid global state** - Components should receive what they need through parameters or injection

### Architecture Principles  
- **No framework mixing** - Don't mix incompatible patterns; use pure modern approaches
- **Proper encapsulation** - Internal state should be truly internal; public interface should be minimal
- **Dependency boundaries** - Controllers/handlers should not directly expose their dependencies to views/templates
- **Clean separation** - Views handle presentation, Controllers handle request logic, Services handle business logic

### Examples: Reusable vs Project-Specific Code

#### Bad: Tightly Coupled Component
```python
# BAD - Hardcoded dependencies, project-specific
class ImageGridController:
    def __init__(self):
        # Hardcoded singleton access
        self.images = AppContainer.image_service.get_images()
        self.columns = APP_SPECIFIC_COLUMNS
        
    def render(self):
        # Hardcoded project-specific styling
        return render_template(
            "grid.html",
            images=self.images,
            background_color=APP_PURPLE
        )
```

#### Good: Reusable Component
```python
# GOOD - Generic, dependency-injected, reusable
from typing import TypeVar, Generic, Callable, List
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class GridConfig:
    columns: int
    background_color: str
    
class ImageGridController(Generic[T]):
    def __init__(
        self,
        items: List[T],
        config: GridConfig,
        item_renderer: Callable[[T], str]
    ):
        self.items = items
        self.config = config
        self.item_renderer = item_renderer
    
    def render(self) -> str:
        rendered_items = [self.item_renderer(item) for item in self.items]
        return render_template(
            "grid.html",
            items=rendered_items,
            config=self.config
        )
```

#### Property Exposure Example
```python
# BAD - Exposing entire service
class UserController:
    auth_service: AuthService  # Exposes entire service

# GOOD - Exposing only what's needed  
class UserController:
    @property
    def current_user_id(self) -> str | None:
        return self._auth_service.current_user.id if self._auth_service.current_user else None
```

#### Reusable Service Design
```python
# BAD - Project-specific service
class AppNameImageService:
    def get_app_name_images(self) -> list[AppNameImage]:
        ...
    def process_app_name_style(self) -> AppNameResult:
        ...

# GOOD - Generic, interface-based service
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

InputT = TypeVar('InputT')
OutputT = TypeVar('OutputT')

class ImageProcessingService(ABC, Generic[InputT, OutputT]):
    @abstractmethod
    async def process_image(self, input_data: InputT) -> OutputT:
        pass

class AIImageProcessor(ImageProcessingService[bytes, ProcessedImage]):
    def __init__(self, api_client: APIClient, endpoint: str):
        self._api_client = api_client
        self._endpoint = endpoint
    
    async def process_image(self, input_data: bytes) -> ProcessedImage:
        response = await self._api_client.post(self._endpoint, data=input_data)
        return ProcessedImage.from_response(response)
```

### Reusability Checklist
Before writing any component, ask:
- ✅ **Can this be used in another project?** Remove app-specific hardcoded values
- ✅ **Are dependencies injected?** Don't access singletons or global state internally
- ✅ **Is the API clean and intuitive?** Could another developer use this without reading implementation?
- ✅ **Does it follow single responsibility?** Each component should do one thing well
- ✅ **Is it generic enough?** Use interfaces and generics where appropriate
- ✅ **Can it be easily tested?** All dependencies should be mockable

This ensures every component is a building block that can be extracted and reused across projects.

## Commands

### Building and Running
- Install dependencies: `pip install -r requirements.txt` or `npm install`
- Run: `python main.py` or `npm start`
- Clean: Remove `__pycache__`, `.pyc` files, or `node_modules`

### Testing
- Run tests: `pytest` or `npm test`
- Coverage: `pytest --cov` or `npm run coverage`

## Architecture

### Core Architecture Pattern
- **MVC/MVVM**: Model-View-Controller or Model-View-ViewModel
- **Dependency Injection**: Uses a container/factory for service registration
- **Data Persistence**: ORM or database abstraction layer

### Key Directories Structure

```
project/
├── app/                        # Application initialization
├── config/                     # Configuration and environment
├── di/                         # Dependency injection container
├── models/                     # Data models and schemas
├── services/                   # Business logic and external integrations
│   ├── api/                   # API service layer
│   ├── auth/                  # Authentication services
│   └── network/               # Core networking
├── controllers/               # Request handlers / ViewModels
├── views/                     # Templates / UI components
└── utils/                     # Utilities and extensions
```

### Service Layer Architecture

#### API Services
- `APIService`: Main API service with token management and auto-refresh
- All API endpoints defined in a central configuration or enum

### Dependency Injection

The `Container` class registers all services:
- Authentication services
- API services (network service, API service)
- Business services
- Database connections
- Controllers/ViewModels (factory methods)

## Micro-SaaS Architecture Standards

### Multi-Tenancy Strategy
- **Isolation First**: Data must be logically or physically isolated per tenant
- **Tenant Context Injection**: Tenant ID should be injected via middleware, never passed manually to functions
- **Row-Level Security (RLS)**: Prefer native RLS policies (e.g., PostgreSQL RLS) over manual `WHERE tenant_id = ?` clauses for stronger security
- **Schema Strategy**:
    - **Pooled (Shared Schema)**: Default for standard SaaS. Uses discriminator column (`tenant_id`). Efficient resource usage.
    - **Siloed (Schema/DB per Tenant)**: Use for enterprise clients requiring strict data isolation or compliance (HIPAA/GDPR).

### Scalability Patterns
- **Stateless Design**: Application servers must be strictly stateless to allow auto-scaling. Store session state in Redis/Memcached.
- **Async Processing**: Offload long-running tasks (reports, bulk imports, AI processing) to background queues (Redis Queue, Celery, SQS).
- **Database Design for Scale**:
    - **Primary Keys**: Use sortable unique IDs like **UUIDv7** or **KSUID** instead of auto-incrementing integers to prevent enumeration and fragmentation.
    - **Partitioning Plan**: Design tables with partitioning keys (e.g., Tenant ID or Time) from day one.
- **Caching Topology**: Implement multi-layer caching:
    1. **CDN/Edge**: Static assets and public content.
    2. **API Gateway**: Idempotent API responses.
    3. **Application Cache**: Expensive computations and session data (Redis).
    4. **Database Buffer**: Optimized query execution.

### API Standards for SaaS
- **Idempotency**: All state-changing endpoints (POST/PUT/PATCH/DELETE) must support `Idempotency-Key` headers to safely retry failed requests.
- **Rate Limiting**: Implement strict rate limiting using Token Bucket or Leaky Bucket algorithms, keyed by Tenant ID or User ID.
- **Versioning**: Use header-based versioning (e.g., `Accept-Version: v1`) or URL versioning. Never break existing clients without a depreciation window.
- **Pagination**: All list endpoints must support cursor-based pagination (avoid offset/limit for large datasets).

## Operational Excellence

### Feature Flags & Rollouts
- **Decouple Deploy from Release**: Use feature flags (LaunchDarkly, Flagsmith, or custom) to deploy code silently and release it gradually.
- **Phased Rollouts**: Release progression: Internal Users -> Beta Tenants -> Canary (1-5%) -> General Availability (100%).
- **Kill Switches**: All non-critical external dependencies/features must be killable via flags without redeploying code.

### Usage Metering & Billing
- **Metering Middleware**: Decouple billing logic from business logic. Use middleware to emit usage events (e.g., "API Request", "Storage Used").
- **Async Reporting**: Metering events should be emitted asynchronously to avoid adding latency to user requests.
- **Quota Enforcement**: Check hard limits at the API Gateway or Edge level before requests reach application logic to save resources.

## Development Guidelines

### Adding New Features
1. Define interfaces/protocols for new services
2. Implement the service following existing patterns
3. Register new services in the DI container
4. Create controllers/viewmodels with dependency injection

### API Integration
1. Add new endpoints to the endpoint configuration
2. Implement required methods (path, method, parameters)
3. Use the API service for authenticated requests

### Adding New Routes/Screens
1. Create controller/viewmodel following existing patterns
2. Create view/template using dependency injection
3. Add factory method in container
4. Update routing configuration

### State Management
- Use immutable data structures where possible
- Store persistent data via the data layer abstraction

### User Feedback & Loading States
- **ALWAYS provide user feedback for async operations** - Every operation must show success or failure feedback
- **No silent failures** - Users must always know if an action succeeded or failed
- **Loading states** - Show appropriate loading indicators during async operations
- **Immediate feedback** - Show success/error messages immediately after operations complete

## Critical Implementation Notes

### Data Processing
- Data should be passed as parameters, not global state
- Fresh instances created for each processing session
- Results stored appropriately for persistence

### Authentication & Authorization
- Auth state should be reactive and trigger navigation changes
- All API requests should include automatic token refresh
- Session management handled centrally

### Error Handling
- Structured error types with recovery actions
- Network errors, auth errors, and validation errors handled differently
- UI provides appropriate retry mechanisms based on error type

## File Naming Conventions
- Views/Pages: `something_page.py` or `SomethingPage.tsx` for full screens
- Controllers: `something_controller.py` or `SomethingController.ts`
- Services: `something_service.py` with matching interface
- Models: Descriptive names like `processed_image.py`, `user_session.py`

## Code Quality & Development Rules

### Core Development Principles
- **Platform Focus**: Know your target platform - don't implement features for platforms you're not targeting
- **Senior-Level Code Quality**: Write reusable, loosely-coupled code that can be reused in other projects
- **Confidence-Based Development**: Do not make changes until you have 95% confidence in the implementation. Ask follow-up questions to gain clarity before proceeding
- **Step-by-Step Thinking**: Always think through problems systematically before implementing solutions

### CRITICAL Interface Update Rule
**MANDATORY: When updating any interface/protocol, ALL implementing types must be updated immediately**

When you modify an interface (add methods, change signatures, etc.), you MUST:

1. **Search for ALL implementing types** using these search patterns:
   - Search for class declarations that implement the interface
   - Search for the interface name in the entire codebase
   - Look for mock implementations, test doubles, and stub classes

2. **Update EVERY implementing type** including:
   - Main implementation classes
   - Mock classes (especially those used for testing)
   - Test doubles and stub implementations
   - Any class that implements the interface

3. **Common locations for implementing types:**
   - `services/` directory - main implementations
   - `mocks/` or `testing/` directories - mock implementations  
   - `tests/` directory - test doubles
   - Extensions or mixins

4. **Verification steps:**
   - Run the type checker/linter to ensure all implementations compile
   - Search for type errors related to interface conformance
   - Check that no implementing type is missing the new methods

**Example workflow:**
```
1. Update interface: `ImageAPIServiceProtocol` 
2. Search for classes implementing the interface
3. Find: `ImageAPIService`, `MockImageAPIService`, `TestImageAPIService`
4. Update ALL found classes with new methods
5. Run type checker to verify all implementations work
```

**This rule prevents runtime errors and ensures interface consistency across the codebase.**

### Best Practices
- **Modern APIs**: Always use the latest stable features and patterns
- **Async Operations**: Implement async/await pattern for all asynchronous operations
- **Code Quality**: Write clean, readable, and well-structured code
- **Imports**: Always import necessary modules at the top of files
- **Type Hints**: Add type hints to all function signatures and variables
- **No TODOs**: Never leave TODO comments in production code
- **No Deprecated APIs**: Avoid using any deprecated or legacy APIs
- **Business Logic Separation**: NEVER put business logic directly in views/templates. ALL business logic, API calls, and data manipulation must be implemented in controllers/services
- **Interface Synchronization**: When adding new methods to a class that implements an interface, ALWAYS add the method definition to the interface first
- **Race Condition Prevention**: NEVER code in a way that creates race conditions. Always ensure that critical operations complete fully before allowing the flow to continue
- **Async Operation UX**: ALWAYS provide UI feedback for async operations

### Code Organization & Structure
- **File Size**: Write small, reusable files - separate code that can be logically split
- **Code Reuse**: Before writing new code, examine existing codebase for reusable components
- **Scope Focus**: Only write code within the requested scope - don't add unnecessary features
- **Complexity Avoidance**: Write simple, understandable code - avoid over-engineering
- **Code Deletion**: Only delete code when absolutely necessary and provide clear justification

### Architecture & Dependency Management
- **Dependency Injection**: Declare all services in a DI container
- **Parameter Passing**: Pass parameters through DI container configuration
- **Controller Isolation**: Each route should have its own controller unless sharing is absolutely necessary
- **Loose Coupling**: Use callbacks/functions in DI containers instead of direct component references

### View & Component Guidelines
- **Component Reusability**: Create UI components that can be reused across projects
- **State Management**: Keep all state in controllers/viewmodels, not in views
- **UI Decoupling**: Build small, reusable UI components with minimal dependencies
- **View Breakdown**: Split large views into smaller components when they become complex
- **Controller Instantiation**: Never instantiate controllers inside view initializers - always use dependency injection
- **Parameter Efficiency**: Pass only required data to components - prefer callbacks/primitives over full objects

### Development Workflow
- **Build Verification**: After completing any code changes, ALWAYS verify there are no errors
- **Lint/Type Check**: Run linters and type checkers before considering work complete
- **Import Standards**: Always include necessary imports at the top of files

### Testing & Quality Assurance
- **Automated Testing**: Write unit tests for business logic
- **Integration Testing**: Test API integrations and external dependencies
- **Code Review**: Ensure all new code follows established patterns and conventions
- **Reusability Testing**: Verify that new components can be extracted and used in other projects

### Code Cleanup Rules
- **Delete Unused Code**: When changing a solution or approach, ALWAYS delete the previous code that's no longer needed
- **Clean Refactoring**: If a better solution is found, remove the old implementation completely
- **No Code Pollution**: Never add debug-specific or temporary code to production classes

### Type Safety Rules
- **ALWAYS Check Types**: Before writing any code, READ the actual type definitions from the codebase
- **No Guessing Parameters**: Never assume parameter names or types. Always verify exact function signatures
- **Read Before Write**: When implementing interfaces or using existing types, READ the actual definitions first
- **Verify Imports**: Make sure all required imports are present for types being used

### Git Workflow
- **Verify Before Commit**: Before committing ANY changes, ALWAYS verify the code works
- **Test Requirement**: Run tests and verify the application works before committing
- **Auto-Commit**: Create a git commit when finishing work, but ONLY after successful verification
- **Commit Process**: After completing any task:
  1. Run linter/type checker to verify no errors
  2. Run tests if available
  3. Run git status and git diff to review changes
  4. Create a descriptive commit message
  5. Commit only if verification was successful
- **Commit Message Format**: Use clear, descriptive messages that explain what was accomplished

### Component Architecture Rules
- **Code Belongs Where It's Used**: Logic for a component's behavior must be implemented INSIDE that component
- **Proper Parameter Passing**: If a component needs different behavior, expose it through clean parameters
- **No External Workarounds**: Never add workarounds outside a component. Modify the component internally

### Dependency Injection Rules
- **Use constructor injection** - Always pass dependencies through constructors
- **All dependencies must be explicit** - No hidden singleton access
- **Service composition happens at the Container level** - Services receive dependencies via constructor

### Architecture Enforcement Rules  
- **Controllers should only know about their direct service dependencies** - Never expose internal service dependencies
- **Caching, networking, and storage details must be hidden behind service interfaces**
- **Before adding any dependency, ask: "Should this component really know about this?"**

### Code Formatting Rules
- **ALWAYS indent code properly** - Use consistent indentation throughout all files
- **Follow language conventions** - Python: 4 spaces, JavaScript/TypeScript: 2 spaces
- **Maintain alignment** - Align related code blocks consistently
- **Use formatters** - Run code formatters (black, prettier) before committing

### Logging Rules
- **ALWAYS add comprehensive logging** - Every significant operation must be logged
- **Log at appropriate levels**:
  - **Info**: Important state changes, initialization, successful operations
  - **Debug**: Detailed information for debugging
  - **Warning**: Potential issues that don't break functionality
  - **Error**: All errors with full context
  - **Critical**: Failures that require immediate attention
- **Log network operations**: Log all network requests and responses
- **Log API calls**: Log all API method calls, parameters, success/failure
- **Include context in logs**: Always include relevant context to make logs actionable
- **Never log sensitive data**: Never log API keys, tokens, passwords, or personal user data

### API Response Handling Rules
- **ALWAYS read API documentation first**: Before creating data models, thoroughly read the official documentation
- **Handle optional fields**: API responses may have different structures across endpoints
- **Default to optional for non-critical fields**: When in doubt, make fields optional
- **Test all endpoints**: Verify the response structure matches your models
- **Use detailed error logging**: Log specific parsing errors to identify issues
- **Validate response structures**: Before parsing, log response previews to verify structure

### JSON/Data Parsing Rules
- **Use consistent naming conventions**: Follow language conventions for property names
- **Handle case conversion**: Use appropriate libraries for snake_case/camelCase conversion
- **Verify parsing**: Test parsing with actual API responses and verify all fields are populated correctly
- **Property naming**: Follow language conventions (snake_case for Python, camelCase for JavaScript)
