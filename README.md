# LightCrafter: PBR-Conditioned Video Diffusion Refinement for Controllable and Consistent Relighting

[Zixin Guo](https://zixinguo.me/)<sup>1</sup>,
[Yehonathan Litman](https://yehonathanlitman.github.io/)<sup>1</sup>,
[Yifeng He](https://www.linkedin.com/in/yifeng-he-502a85158/)<sup>2</sup>,
[John Miller](https://scholar.google.com/citations?hl=en&user=3pO52nwAAAAJ&view_op=list_works&sortby=pubdate)<sup>3</sup>,
[Chuhan Chen](https://sally-chen.github.io/)<sup>1</sup>,
[Deva Ramanan](https://www.cs.cmu.edu/~deva/)<sup>1</sup>

<sup>1</sup>Carnegie Mellon University &nbsp;&nbsp; <sup>2</sup>University of Toronto &nbsp;&nbsp; <sup>3</sup>Bosch Research

### [Project Page](https://zixinguo.me/lightcrafter/) &nbsp;|&nbsp; [arXiv](https://arxiv.org/abs/2607.08016)

---

We reframe video relighting as the translation of a physically-based rendering (PBR) proxy: rather than
directly translating the input video to the target, we translate a PBR rendering of the input under the
target illumination to the final relit video. This bakes the lighting target into the proxy, giving
intricate lighting control and long-form temporal consistency, while a video diffusion refiner adds
hard-to-model effects such as global illumination.

## Code coming soon

We will release our dataset, benchmark, metrics, and code here. Star/watch this repository for updates.

## Citation

If you find our work useful, please consider citing:

```bibtex
@article{guo2026lightcrafter,
  title   = {LightCrafter: PBR-Conditioned Video Diffusion Refinement for Controllable and Consistent Relighting},
  author  = {Guo, Zixin and Litman, Yehonathan and He, Yifeng and Miller, John and Chen, Chuhan and Ramanan, Deva},
  journal = {arXiv preprint arXiv:2607.08016},
  year    = {2026}
}
```
