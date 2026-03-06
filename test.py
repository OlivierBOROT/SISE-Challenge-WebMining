import numpy as np

pca = np.load("data/models/X_pca.npy")
print(type(pca))
# print({
#             "x": pca[:, 0].tolist(),
#             "y": pca[:, 1].tolist()
#         })

print(len(pca[:, 0].tolist()))