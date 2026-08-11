"""Unit tests for Material domain model and repository."""

from datetime import datetime

import pytest

from app.core.exceptions import EntityHasDependenciesError
from app.domain.entities import Material
from app.domain.production.material import MaterialCreate, MaterialType, MaterialUpdate
from app.repositories.production_repository import MaterialRepository


class TestMaterialModel:
    def test_material_creation(self, session, sample_material):
        assert sample_material.id is not None
        assert sample_material.material_code == "MAT-BEER-600"
        assert sample_material.material_name == "Beer 600ml"
        assert sample_material.material_type == "FINISHED_PRODUCT"
        assert sample_material.base_unit == "L"
        assert sample_material.plant == "P001"
        assert sample_material.is_active is True
        assert sample_material.created_at is not None

    def test_material_unique_code(self, session, sample_material):
        repo = MaterialRepository(session)
        with pytest.raises(Exception):
            repo.create(
                MaterialCreate(
                    material_code="MAT-BEER-600",
                    material_name="Another Beer",
                    material_type=MaterialType.FINISHED_PRODUCT,
                    base_unit="L",
                    plant="P001",
                )
            )

    def test_material_inactive(self, session, sample_material):
        sample_material.is_active = False
        session.flush()
        repo = MaterialRepository(session)
        result = repo.get_by_id(sample_material.id)
        assert result.is_active is False


class TestMaterialRepository:
    def test_create_material(self, session):
        repo = MaterialRepository(session)
        material = repo.create(
            MaterialCreate(
                material_code="MAT-RAWMALT-001",
                material_name="Raw Malt",
                material_type=MaterialType.RAW_MATERIAL,
                base_unit="KG",
                plant="P001",
            )
        )
        assert material.id is not None
        assert material.material_code == "MAT-RAWMALT-001"

    def test_get_by_code(self, session, sample_material):
        repo = MaterialRepository(session)
        found = repo.get_by_code("MAT-BEER-600")
        assert found is not None
        assert found.id == sample_material.id

    def test_get_by_code_not_found(self, session):
        repo = MaterialRepository(session)
        found = repo.get_by_code("NONEXISTENT")
        assert found is None

    def test_update_material(self, session, sample_material):
        repo = MaterialRepository(session)
        updated = repo.update(
            sample_material.id,
            MaterialUpdate(material_name="Premium Beer 600ml"),
        )
        assert updated is not None
        assert updated.material_name == "Premium Beer 600ml"

    def test_list_active(self, session, sample_material):
        repo = MaterialRepository(session)
        inactive = repo.create(
            MaterialCreate(
                material_code="MAT-INACTIVE",
                material_name="Inactive Material",
                material_type=MaterialType.RAW_MATERIAL,
                base_unit="KG",
                plant="P001",
            )
        )
        inactive.is_active = False
        session.flush()

        active = repo.list_active()
        assert len(active) == 1
        assert active[0].material_code == "MAT-BEER-600"

    def test_delete_material(self, session, sample_material):
        repo = MaterialRepository(session)
        result = repo.delete(sample_material.id)
        assert result is True
        assert repo.get_by_id(sample_material.id) is None

    def test_delete_not_found(self, session):
        repo = MaterialRepository(session)
        result = repo.delete(9999)
        assert result is False

    def test_count_active(self, session, sample_material):
        repo = MaterialRepository(session)
        assert repo.count_active() == 1
        inactive = repo.create(
            MaterialCreate(
                material_code="MAT-INACTIVE",
                material_name="Inactive Material",
                material_type=MaterialType.RAW_MATERIAL,
                base_unit="KG",
                plant="P001",
            )
        )
        inactive.is_active = False
        session.flush()
        assert repo.count_active() == 1

    def test_delete_material_with_dependencies_raises(self, session, sample_material, sample_recipe):
        repo = MaterialRepository(session)
        with pytest.raises(EntityHasDependenciesError):
            repo.delete(sample_material.id)


class TestMaterialPydantic:
    def test_material_create_validation(self):
        material = MaterialCreate(
            material_code="MAT-TEST-001",
            material_name="Test Material",
            material_type=MaterialType.FINISHED_PRODUCT,
            base_unit="PC",
            plant="P001",
        )
        assert material.material_code == "MAT-TEST-001"
        assert material.material_type == MaterialType.FINISHED_PRODUCT

    def test_material_create_empty_code_fails(self):
        with pytest.raises(Exception):
            MaterialCreate(
                material_code="",
                material_name="Test",
                material_type=MaterialType.FINISHED_PRODUCT,
                base_unit="PC",
                plant="P001",
            )
