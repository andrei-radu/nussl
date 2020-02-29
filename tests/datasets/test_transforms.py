import pytest
from nussl.datasets import transforms
from nussl.datasets.transforms import TransformException
import nussl
from nussl import STFTParams, evaluation
import numpy as np
from nussl.core.masks import BinaryMask, SoftMask
import itertools
import copy

stft_tol = 1e-6

def separate_and_evaluate(mix, sources, mask_data):
    estimates = []
    mask_data = normalize_masks(mask_data)
    for i in range(mask_data.shape[-1]):
        mask = SoftMask(mask_data[..., i])
        estimate = mix.apply_mask(mask)
        estimate.istft()
        estimates.append(estimate)

    assert np.allclose(
        sum(estimates).audio_data, mix.audio_data, atol=stft_tol)

    sources = [sources[k] for k in sources]
    evaluator = evaluation.BSSEvalScale(
        sources, estimates)
    scores = evaluator.evaluate()
    return scores

def normalize_masks(mask_data):
    mask_data = (
        mask_data / 
        np.sum(mask_data, axis=-1, keepdims=True) + 1e-8
    )
    return mask_data

def test_transform_msa_psa(musdb_tracks):
    track = musdb_tracks[10]
    mix, sources = nussl.utils.musdb_track_to_audio_signals(track)

    data = {
        'mix': mix,
        'sources': sources
    }

    msa = transforms.MagnitudeSpectrumApproximation()
    psa = transforms.PhaseSensitiveSpectrumApproximation()

    assert msa.__class__.__name__ in str(msa)
    assert psa.__class__.__name__ in str(psa)

    pytest.raises(TransformException, psa, {'mix': 'blah'})
    pytest.raises(TransformException, msa, {'mix': 'blah'})

    output = msa(data)
    assert np.allclose(output['mix_magnitude'], np.abs(mix.stft()))
    assert list(data['sources'].keys()) == sorted(list(sources.keys()))

    masks = []
    estimates = []

    shape = mix.stft_data.shape + (len(sources),)

    mix_masks = np.ones(shape)
    mix_scores = separate_and_evaluate(mix, data['sources'], mix_masks)

    ibm_scores = separate_and_evaluate(
        mix, data['sources'], data['ideal_binary_mask'])
    output['source_magnitudes'] += 1e-8

    mask_data = (
        output['source_magnitudes'] / 
        np.maximum(
            output['mix_magnitude'][..., None], 
            output['source_magnitudes'])
    )
    msa_scores = separate_and_evaluate(mix, data['sources'], mask_data)

    output = psa(data)
    assert np.allclose(output['mix_magnitude'], np.abs(mix.stft()))
    assert list(data['sources'].keys()) == sorted(list(sources.keys()))

    output['source_magnitudes'] += 1e-8

    mask_data = (
        output['source_magnitudes'] / 
        np.maximum(
            output['mix_magnitude'][..., None], 
            output['source_magnitudes'])
    )
    psa_scores = separate_and_evaluate(mix, data['sources'], mask_data)

    for key in msa_scores:
        if key in ['SDR', 'SIR', 'SAR']:
            diff = np.array(psa_scores[key]) - np.array(mix_scores[key])
            assert diff.mean() > 10

def test_transform_sum_sources(musdb_tracks):
    track = musdb_tracks[10]
    mix, sources = nussl.utils.musdb_track_to_audio_signals(track)

    data = {
        'mix': mix,
        'sources': sources
    }

    groups = itertools.combinations(data['sources'].keys(), 3)

    for group in groups:
        _data = copy.deepcopy(data)
        tfm = transforms.SumSources([group])
        _data = tfm(_data)
        for g in group:
            assert g not in _data['sources']
        assert 'group0' in _data['sources']

        summed_sources = sum([sources[k] for k in group])

        assert np.allclose(
            _data['sources']['group0'].audio_data,
            summed_sources.audio_data
        )

    pytest.raises(TransformException, tfm, {'no_key'})

    pytest.raises(TransformException, 
        transforms.SumSources, 'test')

    pytest.raises(TransformException,   
        transforms.SumSources, 
        [['vocals', 'test'], ['test2', 'test3']],
        ['mygroup']
    )

def test_transform_compose(musdb_tracks):
    track = musdb_tracks[10]
    mix, sources = nussl.utils.musdb_track_to_audio_signals(track)

    data = {
        'mix': mix,
        'sources': sources
    }

    msa = transforms.MagnitudeSpectrumApproximation()
    tfm = transforms.SumSources(
        [['other', 'drums', 'bass']],
        group_names=['accompaniment']
    )
    com = transforms.Compose([tfm, msa])
    assert msa.__class__.__name__ in str(com)
    assert tfm.__class__.__name__ in str(com)

    data = com(data)

    assert np.allclose(data['mix_magnitude'], np.abs(mix.stft()))

    mask_data = (
        data['source_magnitudes'] / 
        np.maximum(
            data['mix_magnitude'][..., None], 
            data['source_magnitudes'])
    )
    msa_scores = separate_and_evaluate(mix, data['sources'], mask_data)
    shape = mix.stft_data.shape + (len(sources),)
    mask_data = np.ones(shape)
    mix_scores = separate_and_evaluate(mix, data['sources'], mask_data)

    for key in msa_scores:
        if key in ['SDR', 'SIR', 'SAR']:
            diff = np.array(msa_scores[key]) - np.array(mix_scores[key])
            assert diff.mean() > 10

def test_transform_to_dataloader(musdb_tracks):
    track = musdb_tracks[10]
    mix, sources = nussl.utils.musdb_track_to_audio_signals(track)

    data = {
        'mix': mix,
        'sources': sources
    }

    msa = transforms.MagnitudeSpectrumApproximation()
    tdl = transforms.ToDataLoader()
    assert tdl.__class__.__name__ in str(tdl)

    com = transforms.Compose([msa, tdl])

    data = com(data)
    accepted_keys = ['mix_magnitude', 'source_magnitudes']
    rejected_keys = ['mix', 'sources']

    for a in accepted_keys:
        assert a in data
    for r in rejected_keys:
        assert r not in data