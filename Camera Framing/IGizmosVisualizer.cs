using System;

namespace Carlos {
    public interface IGizmosVisualizer : ISystem {
        public void AddGizmosCallback(Action callback);
        public bool RemoveGizmosCallback(Action callback);
        public void ClearAll();
    }
}
