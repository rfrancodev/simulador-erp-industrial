"""Domain exceptions for business rule violations and error translation."""


class DomainError(Exception):
    """Base class for domain-level errors."""


class EntityNotFoundError(DomainError):
    def __init__(self, entity: str, identifier) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} with identifier {identifier!r} was not found")


class DuplicateEntityError(DomainError):
    def __init__(self, entity: str, identifier) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} with identifier {identifier!r} already exists")


class DatabaseIntegrityError(DomainError):
    def __init__(self, entity: str) -> None:
        self.entity = entity
        super().__init__(
            f"{entity} could not be saved because it violates a database constraint"
        )


class RecipeMaterialMismatchError(DomainError):
    def __init__(self, recipe_id: int, recipe_material_id: int, order_material_id: int) -> None:
        self.recipe_id = recipe_id
        super().__init__(
            "Recipe and Production Order reference different materials "
            f"(recipe_material_id={recipe_material_id}, order_material_id={order_material_id})"
        )


class ComponentUnitMismatchError(DomainError):
    def __init__(self, component_material_id: int, unit: str, base_unit: str) -> None:
        self.component_material_id = component_material_id
        super().__init__(
            f"Component material {component_material_id!r} unit {unit!r} does not match "
            f"its base unit {base_unit!r}"
        )


class EntityHasDependenciesError(DomainError):
    def __init__(self, entity: str, identifier, dependencies: list[str]) -> None:
        self.entity = entity
        super().__init__(
            f"{entity} with identifier {identifier!r} cannot be deleted because it is "
            f"referenced by: {', '.join(dependencies) or 'unknown dependencies'}"
        )


class InvalidStateTransitionError(DomainError):
    def __init__(self, entity: str, current, target, allowed: set) -> None:
        self.entity = entity
        self.current = current
        self.target = target
        allowed_list = ", ".join(sorted(_state_name(a) for a in allowed)) or "none"
        super().__init__(
            f"Invalid {entity} state transition: {_state_name(current)} -> {_state_name(target)}. "
            f"Allowed: {allowed_list}"
        )


class BatchNotCompletedError(DomainError):
    def __init__(self, batch_id: int, current_status: str) -> None:
        self.batch_id = batch_id
        self.current_status = current_status
        super().__init__(
            f"Batch {batch_id} is not COMPLETED (current status: {current_status!r}). "
            "Final quality inspection results require the batch to be COMPLETED."
        )


def _state_name(value) -> str:
    return getattr(value, "value", str(value))
