from lingua.config import Config, load_config, save_config


def test_config_roundtrip(tmp_path) -> None:
    config = Config(model='@preset/test"quote', batch_size=3)
    path = save_config(tmp_path, config)
    assert path.exists()
    loaded = load_config(tmp_path)
    assert loaded.model == config.model
    assert loaded.batch_size == 3

