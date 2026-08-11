"""Unit tests for PP-PI — ProductionRecipe repository."""

from app.repositories.production_repository import ProductionRecipeRepository


class TestProductionRecipeRepository:
    def test_get_by_code(self, session, sample_recipe):
        repo = ProductionRecipeRepository(session)
        found = repo.get_by_code("REC-BEER-001")
        assert found is not None
        assert found.id == sample_recipe.id

    def test_get_by_code_not_found(self, session):
        repo = ProductionRecipeRepository(session)
        assert repo.get_by_code("NONEXISTENT") is None

    def test_get_active_for_material(self, session, sample_recipe, sample_material):
        repo = ProductionRecipeRepository(session)
        recipes = repo.get_active_for_material(sample_material.id)
        assert len(recipes) == 1
        assert recipes[0].recipe_code == "REC-BEER-001"

    def test_get_active_for_material_empty(self, session, sample_material):
        repo = ProductionRecipeRepository(session)
        assert repo.get_active_for_material(sample_material.id) == []