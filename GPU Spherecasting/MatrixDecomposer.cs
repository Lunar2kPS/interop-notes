using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace Carlos {
    /// <summary>
    /// Utility class for performing all the necessary mathematical operations for decomposing a 4x4 matrix.
    /// </summary>
    /// <remarks>
    /// <para>Note that Unity's <see cref="Matrix4x4"/> struct uses fields like "m00", "m01", and "m02" to represent mXY in row X, column Y, and they are stored as continguous columns (column 0 fields first, then column 1 fields, etc.).</para>
    /// </remarks>
    public static class MatrixDecomposer {
        public static readonly Regex Matrix4x4StringPattern = new("^(-?[0-9]+\\.?[0-9]*(e-?[0-9]+)?\\s+){15}-?[0-9]+\\.?[0-9]*$");

        /// <summary>
        /// Decompose a 4x4 transform matrix (16 space-separated floats, column-major) into Unity position, rotation, and scale.
        /// </summary>
        /// <param name="transformString">Space-separated list of 16 floats (e.g. "-1 0 0 0 0 0 1 0 0 1 0 0 1.14 -0.55 1.04 1") representing the 4x4 matrix.</param>
        /// <returns>True if parsing and decomposition succeeded.</returns>
        public static bool DecomposeTransform(string transformString, out Vector3 position, out Quaternion rotation, out Vector3 scale) {
            position = Vector3.zero;
            rotation = Quaternion.identity;
            scale = Vector3.one;
            if (string.IsNullOrWhiteSpace(transformString))
                return false;
            string[] parts = transformString.Trim().Split((char[]) null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != 16)
                return false;
            float[] arrayMatrix = new float[16];
            for (int i = 0; i < 16; i++) {
                if (!float.TryParse(parts[i], out arrayMatrix[i]))
                    return false;
            }

            Matrix4x4 matrix = ArrayToMatrix(arrayMatrix);
            return DecomposeTransform(matrix, out position, out rotation, out scale);
        }

        public static bool DecomposeTransform(Matrix4x4 transform, out Vector3 position, out Quaternion rotation, out Vector3 scale) {
            position = Vector3.zero;
            rotation = Quaternion.identity;
            scale = Vector3.one;

            Matrix4x4 rotationMatrix = RotationMatrix(transform);
            scale = ScaleFromMatrix(rotationMatrix);
            rotation = QuaternionFromMatrix(rotationMatrix);
            position = TranslationFromMatrix(transform);
            return true;
        }

        private static Vector3 TranslationFromMatrix(Matrix4x4 matrix) {
            //TODO: Document our position coordinate switch:
            Vector3 position = new Vector3();
            position.x = matrix.m03;
            position.y = matrix.m23;
            position.z = matrix.m13;

            Vector3 newPos = new(position.x, position.z, position.y);
            return newPos;
        }
        /// <summary>
        /// Gets the length of the x, y, and z columns and assigns value to scale vector respectively
        /// </summary>
        /// <param name="matrix"></param>
        /// <returns></returns>
        private static Vector3 ScaleFromMatrix(Matrix4x4 matrix) {
            Vector3 scale = new();

            scale.x = matrix.GetColumn(0).magnitude;
            scale.y = matrix.GetColumn(1).magnitude;
            scale.z = matrix.GetColumn(2).magnitude;

            Vector3 newScale = new Vector3(scale.x, scale.y, scale.z);
            return newScale;
        }
        /// <summary>
        /// Converts the original matrix into a rotation matrix
        /// </summary>
        /// <param name="matrix"></param>
        /// <param name="scale"></param>
        /// <returns></returns>
        private static Matrix4x4 RotationMatrix(Matrix4x4 matrix) {
            Matrix4x4 rotationMatrix = new();
            rotationMatrix.SetColumn(0, matrix.GetColumn(0));
            rotationMatrix.SetColumn(1, matrix.GetColumn(1));
            rotationMatrix.SetColumn(2, matrix.GetColumn(2));
            rotationMatrix.SetColumn(3, new Vector4(0, 0, 0, 1));
            return rotationMatrix;
        }
        /// <summary>
        /// Converts this rotation matrix into a Quaternion
        /// </summary>
        /// <param name="matrix"></param>
        /// <returns></returns>
        private static Quaternion QuaternionFromMatrix(Matrix4x4 matrix) {
            Quaternion q = new Quaternion();
            q.w = Mathf.Sqrt(Mathf.Max(0, 1 + matrix.m00 + matrix.m11 + matrix.m22)) / 2;
            q.x = Mathf.Sqrt(Mathf.Max(0, 1 + matrix.m00 - matrix.m11 - matrix.m22)) / 2;
            q.y = Mathf.Sqrt(Mathf.Max(0, 1 - matrix.m00 + matrix.m11 - matrix.m22)) / 2;
            q.z = Mathf.Sqrt(Mathf.Max(0, 1 - matrix.m00 - matrix.m11 + matrix.m22)) / 2;

            q.x *= Mathf.Sign(q.x * (matrix.m21 - matrix.m12));
            q.y *= Mathf.Sign(q.y * (matrix.m02 - matrix.m20));
            q.z *= Mathf.Sign(q.z * (matrix.m10 - matrix.m01));

            Quaternion adjustment = Quaternion.Euler(0, 180, 0);
            Quaternion newQuat = new Quaternion(-q.x, -q.z, -q.y, q.w);

            return adjustment * newQuat * adjustment;
        }

        /// <summary>
        /// Takes a 16 element array and reshapes it into a 4x4 matrix.
        /// </summary>
        private static Matrix4x4 ArrayToMatrix(float[] array) {
            Matrix4x4 matrix = new();
            int i = 0;
            for (int column = 0; column < 4; column++) {
                matrix.SetColumn(column, new Vector4(array[i], array[i + 1], array[i + 2], array[i + 3]));
                i += 4;
            }
            return matrix;
        }
    }
}
