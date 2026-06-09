import math
import random
import numpy as np

class DiarizationClustering:
    def __init__(self, margin=0.5):
        self.margin = margin

    @staticmethod
    def cosine_similarity(v1, v2):
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))
        return dot / (mag1 * mag2) if mag1 * mag2 > 0 else 0.0

    def kmeans_clustering(self, vectors, k=2, max_iter=10):
        if not vectors or k <= 0: return [], []
        if len(vectors) <= k: return list(range(len(vectors))), vectors
        centroids = random.sample(vectors, k)
        labels = []
        for _ in range(max_iter):
            labels = []
            clusters = [[] for _ in range(k)]
            for v in vectors:
                sims = [self.cosine_similarity(v, c) for c in centroids]
                best_idx = sims.index(max(sims))
                labels.append(best_idx)
                clusters[best_idx].append(v)
            for i in range(k):
                if clusters[i]:
                    dim = len(vectors[0])
                    centroids[i] = [sum(c[d] for c in clusters[i]) / len(clusters[i]) for d in range(dim)]
        return labels, centroids

    def pca_reduce(self, vectors, dims=2):
        if not vectors: return []
        if len(vectors) < 2: return [v[:dims] for v in vectors]
        try:
            X = np.array(vectors)
            X_centered = X - X.mean(axis=0)
            if np.all(X_centered == 0): return [v[:dims] for v in vectors]
            cov = np.cov(X_centered, rowvar=False)
            eig_vals, eig_vecs = np.linalg.eigh(cov)
            idx = np.argsort(eig_vals)[::-1]
            top_vecs = eig_vecs[:, idx[:dims]]
            return np.dot(X_centered, top_vecs).tolist()
        except:
            return [v[:dims] for v in vectors]

    def perform_clustering(self, dia_vectors_list, k_speakers=2):
        """
        Applies K-Means clustering and PCA dimension reduction on Vosk embeddings.
        Returns: labels, centroids, pca_coords
        """
        if not dia_vectors_list:
            return [], [], []
            
        labels, centroids = self.kmeans_clustering(dia_vectors_list, k=k_speakers)
        pca_coords = self.pca_reduce(dia_vectors_list)
        
        return labels, centroids, pca_coords
